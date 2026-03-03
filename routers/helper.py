"""
helper.py — MindWay AI 헬퍼 모듈 (완성본)
================================================
역할  : 상담사 채팅 화면에서 내담자의 최근 발화(슬라이딩 윈도우)를
        분석하여 상담사의 판단을 돕는 참고 정보 + 클릭 삽입용 응답 초안 3개를 제공한다.

구조  : [설정] → [HCX 클라이언트] → [룰 엔진] → [서비스] → [라우터]

주의  : 본 모듈은 상담사의 의사결정을 보조하는 참고 도구이며,
        진단·처방·상담 개입의 주체는 반드시 상담사 본인이다.
        AI는 어떠한 경우에도 상담사의 권한을 대행하거나
        내담자에게 직접 응답하지 않는다.

API키 : HCX_API_KEY는 .env에 순수 키값만 저장. Bearer 조합은 코드에서 처리.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import find_dotenv, load_dotenv
from fastapi import APIRouter
from pydantic import BaseModel, Field

load_dotenv(find_dotenv())


# =============================================================
# 1. 설정 — 환경변수 중앙 관리
# =============================================================

class HCXConfig:
    """HyperCLOVA X 연결 설정. .env 값을 한 곳에서 관리한다."""

    host:       str  = os.getenv("HCX_HOST",           "https://clovastudio.stream.ntruss.com").strip()
    model:      str  = os.getenv("HCX_MODEL",          "HCX-DASH-002").strip()
    api_key:    str  = os.getenv("HCX_API_KEY",        "").strip()
    request_id: str  = os.getenv("HCX_REQUEST_ID",     "mindway-helper").strip()
    timeout:    int  = int(os.getenv("HCX_TIMEOUT",    "20") or "20")
    version:    str  = os.getenv("HCX_API_VERSION",    "v3").strip()
    use_hcx:    bool = os.getenv("USE_HCX",            "0").strip() == "1"

    # 분석에 사용할 최근 발화 개수 (기본 5개, .env의 HCX_HISTORY_WINDOW로 조정 가능)
    history_window: int = int(os.getenv("HCX_HISTORY_WINDOW", "5") or "5")

    @classmethod
    def endpoint(cls) -> str:
        """실제 호출 URL을 조합하여 반환"""
        return f"{cls.host}/{cls.version}/chat-completions/{cls.model}"

    @classmethod
    def auth_header(cls) -> str:
        """
        .env에 순수 키값만 저장하는 규칙을 지원한다.
        이미 'Bearer '가 포함된 경우 그대로, 아니면 자동으로 조합한다.
        """
        key = cls.api_key
        if not key:
            raise RuntimeError("HCX_API_KEY가 비어 있습니다. .env 파일을 확인하세요.")
        if key.lower().startswith("bearer "):
            return key
        return f"Bearer {key}"


# =============================================================
# 2. 시스템 프롬프트 (분석 + 개입 방향 + 클릭 삽입용 초안 대사)
# =============================================================

SYSTEM_PROMPT = """
너는 심리상담사의 의사결정을 실시간으로 보조하는 'AI 헬퍼'다.
너는 상담사 대신 말하거나 내담자에게 직접 답하지 않는다.
너는 상담사가 다음 개입을 결정할 수 있도록 분석 정보를 제공한다.

[절대 규칙]
- 출력은 반드시 JSON 한 줄만. (설명/문장/마크다운/코드블록 금지)
- JSON은 반드시 파싱 가능해야 한다. 따옴표/쉼표 누락 금지.
- 필수 키: insight, emotions, intent, risk, suggestions, reply_candidates (누락 금지)
- emotions는 문자열 리스트 2개 이상.
- risk.level은 "Normal" 또는 "Caution" 또는 "High" 중 하나.
- suggestions는 길이 3의 리스트, 각 원소는 {"type": "...", "rationale": "...", "direction": "..."} 형태.
- reply_candidates는 길이 3의 리스트, 각 원소는 {"text":"...", "why":"..."} 형태.
- 진단/처방/의학적 단정 금지.

[안전 규칙]
- 자해/자살/타해/학대/응급 징후가 있으면 risk.level="High".
- High일 때는 안전 확인 개입이 필요함을 risk.message에 안내.
- 내담자 고통(우울/불안/무력감) 자체는 상담 거부로 단정하지 않는다.

[suggestions 작성 규칙 - 매우 중요]
suggestions는 상담사에게 전달하는 "개입 방향 힌트"다.
- 상담 대사(내담자에게 직접 할 말)를 쓰지 않는다.
- 상담사가 취할 수 있는 개입 전략/질문 방향/주의사항을 간결하게 쓴다.
- type: 개입 유형 (예: 공감 심화, 회피 탐색, 목표 재확인, 자원 탐색, 위험 모니터링)
- rationale: 이 개입이 필요한 이유 (내담자 발화에서 근거 제시)
- direction: 상담사가 취할 수 있는 구체적 방향 (1~2문장, 전략 서술)

[reply_candidates 작성 규칙 - 클릭 삽입용]
reply_candidates는 상담사가 "입력창에 삽입한 뒤 약간 수정해서" 내담자에게 보낼 수 있는 '초안 대사'다.
- 반드시 내담자에게 직접 말하는 문장으로 작성한다. (지침/설명/메타 발화 금지)
- 각 text는 1~2문장, 존댓말, 차분하고 자연스러운 톤.
- 기본 구조 권장: 공감/반영 1문장 + 탐색 질문 1문장.
- "~하세요", "~해보세요", "표현하세요" 같은 지시형/설명형 문장 금지.
- 과도한 단정 금지: "당신은 ~입니다" 같은 판단/진단 표현 금지.
- why에는 해당 문장이 적절한 근거를 내담자 발화 기반으로 짧게 쓴다.

[반드시 이 스키마 그대로]
{
  "insight": "내담자 발화 핵심 요약 (한 문장)",
  "emotions": ["감정1","감정2"],
  "intent": "내담자의 욕구/의도 추정 (단정 금지)",
  "risk": {
    "level": "Normal|Caution|High",
    "signals": ["근거1","근거2"],
    "message": "상담사에게 전달할 짧은 안내"
  },
  "suggestions": [
    {"type":"공감 심화","rationale":"근거","direction":"전략 방향"},
    {"type":"탐색","rationale":"근거","direction":"전략 방향"},
    {"type":"목표/다음단계","rationale":"근거","direction":"전략 방향"}
  ],
  "reply_candidates": [
    {"text":"내담자에게 보낼 1~2문장", "why":"근거"},
    {"text":"내담자에게 보낼 1~2문장", "why":"근거"},
    {"text":"내담자에게 보낼 1~2문장", "why":"근거"}
  ]
}

[확신이 없으면]
- risk.level은 "Caution"
- 나머지는 빈칸 없이 최대한 채워서 출력하라.
""".strip()


# =============================================================
# 3. Pydantic 스키마
# =============================================================

class HelperRequest(BaseModel):
    """
    POST /helper/suggestion 요청 바디.

    Fields:
        sess_id             : 상담 세션 ID
        counselor_id        : 상담사 ID
        last_client_text    : 내담자의 현재(가장 최근) 발화
        last_counselor_text : 상담사의 직전 발화 (선택, 말투/흐름 힌트)
        history             : 이전 대화 목록
                              [{"role": "counselor"|"client", "text": "..."}]
                              최근 HCX_HISTORY_WINDOW개 발화를 슬라이딩 윈도우로 사용
        context             : 추가 컨텍스트 (선택)
    """
    session_id:          int                            = Field(..., alias="sess_id", ge=1)
    counselor_id:        int                            = Field(..., ge=1)
    last_client_text:    str                            = Field(default="")
    last_counselor_text: str                            = Field(default="")
    history:             Optional[List[Dict[str, str]]] = None
    context:             Optional[Dict[str, Any]]       = None

    model_config = {"populate_by_name": True}


# =============================================================
# 4. 룰 기반 1차 필터 (HCX 호출 전 선별)
# =============================================================

_NEG_KEYWORDS: Tuple[str, ...] = (
    "그만", "포기", "싫어", "힘들", "못하겠",
    "안 할래", "의미없", "상담 의미", "돈 아깝",
    "다음에", "취소", "안 올", "안 가", "불필요",
    "죽고싶",
)
_HIGH_RISK_KEYWORDS: Tuple[str, ...] = (
    "죽고싶", "자해", "사라지고싶", "없어지고싶", "끝내고싶",
    "극단적", "목숨",
)

# 클릭 삽입용 후보 문장에 들어가면 어색해지는 "지침형" 금지 패턴
_FORBIDDEN_DIRECTIVE_RE = re.compile(r"(하세요|해보세요|표현하세요|권장합니다|필요합니다|좋습니다\.)")


def _make_rule_reply_candidates(client_text: str, risk_level: str) -> List[Dict[str, str]]:
    """
    HCX 없이도 UI가 동작하도록 하는 최소 품질의 클릭 삽입용 초안.
    (상담사가 수정 가능한 전제)
    """
    t = (client_text or "").strip()

    if risk_level == "High":
        return [
            {"text": "말씀해주셔서 감사합니다. 지금 혹시 스스로를 해치고 싶은 마음이 드는지, 안전은 괜찮으신지 먼저 확인해도 될까요?", "why": "고위험 키워드 감지로 안전 확인 필요"},
            {"text": "지금 이 순간 혼자 견디기 너무 버거울 수 있어요. 주변에 바로 연락할 수 있는 사람이 있거나 안전한 곳에 계신지 알려주실 수 있을까요?", "why": "즉시 안전 확보 및 자원 확인"},
            {"text": "제가 함께 상황을 정리해볼게요. 지금 가장 위험하게 느껴지는 순간이 언제인지, 그리고 그때 어떤 생각이 드는지 말씀해주실 수 있나요?", "why": "위험 신호 구체화 및 모니터링"},
        ]

    if not t:
        return [
            {"text": "괜찮으시면 지금 마음 상태를 한 단어로 표현해주실 수 있을까요?", "why": "발화 없음/짧음 → 상태 파악 질문"},
            {"text": "지금 이 대화에서 가장 다루고 싶은 주제가 있다면 어떤 건지 알려주셔도 좋아요.", "why": "목표/의제 설정"},
            {"text": "말로 설명하기 어렵다면, 최근에 가장 부담됐던 순간 하나만 떠올려볼까요?", "why": "구체 장면 탐색 유도"},
        ]

    # Caution/Normal 공통 템플릿(상담사가 수정 전제로 무난한 초안)
    return [
        {"text": "말씀을 들으니 요즘 많이 지치신 느낌이 있어요. 특히 어떤 상황에서 그 감정이 가장 크게 느껴지셨나요?", "why": "감정 반영 + 촉발 상황 탐색"},
        {"text": "그런 흐름이 계속되면 마음이 무거울 수 있어요. 최근에 조금이라도 덜 힘들었던 순간이 있었는지 함께 찾아볼까요?", "why": "예외/자원 탐색"},
        {"text": "지금 가장 우선으로 바뀌었으면 하는 한 가지가 있다면 무엇인지 여쭤봐도 될까요?", "why": "목표/우선순위 확인"},
    ]


def _make_rule_suggestions(client_text: str, risk_level: str) -> List[Dict[str, str]]:
    """
    상담사용 개입 방향 힌트(대사 금지). 룰-only 또는 fallback에서도 유지.
    """
    t = (client_text or "").strip()

    if risk_level == "High":
        return [
            {"type": "위험 모니터링", "rationale": "고위험 키워드 감지", "direction": "즉시 안전 확인(자해/자살 사고, 계획, 수단 접근성) 및 보호자/기관 연계 가능성 점검"},
            {"type": "안전 자원 탐색", "rationale": "위기 상황 가능성", "direction": "현재 위치/혼자 여부/연락 가능한 사람/즉시 도움 받을 수 있는 자원 확인"},
            {"type": "정서 안정화", "rationale": "정서 과부하 가능", "direction": "호흡/그라운딩 등 즉각적 안정화 후 구체 상황을 짧게 구조화하여 탐색"},
        ]

    if not t:
        return [
            {"type": "라포/열기", "rationale": "내담자 발화 없음", "direction": "대화 진입을 돕는 가벼운 질문으로 현재 상태/의제 설정"},
            {"type": "의제 설정", "rationale": "정보 부족", "direction": "오늘 가장 다루고 싶은 주제/우선순위를 확인"},
            {"type": "구체화", "rationale": "내용 부족", "direction": "최근 장면 1개를 기준으로 감정/생각/상황을 단계적으로 확인"},
        ]

    if risk_level == "Caution":
        return [
            {"type": "회피/이탈 탐색", "rationale": "부정/회피 키워드 감지", "direction": "상담에 대한 기대/부담/저항 지점을 안전하게 탐색(단정 금지)"},
            {"type": "공감 심화", "rationale": "지치거나 무력한 정서 가능", "direction": "감정 반영 후 부담이 큰 지점을 구체 상황으로 좁혀 확인"},
            {"type": "목표/다음단계", "rationale": "동기 저하 가능", "direction": "이번 대화에서 최소한 얻고 싶은 것 1가지를 합의하고 작게 진행"},
        ]

    # Normal
    return [
        {"type": "공감 심화", "rationale": "정서 표현 가능", "direction": "정서의 강도/맥락을 확인하여 내담자 경험을 명료화"},
        {"type": "탐색", "rationale": "핵심 주제 추정 필요", "direction": "업무/관계/생활 중 가장 영향이 큰 영역을 좁혀 구체 장면 탐색"},
        {"type": "목표/다음단계", "rationale": "진행 구조 필요", "direction": "단기 목표를 합의하고 다음 회기까지 관찰/기록 포인트 설정"},
    ]


def rule_check(text: str) -> Dict[str, Any]:
    """
    발화를 키워드 기반으로 1차 분류한다.

    Returns dict with keys:
        skip_hcx      (bool) : True이면 HCX 호출 없이 바로 반환
        churn_signal  (int)  : 이탈/위험 신호 여부 (0 or 1)
        type          (str)  : NORMAL | CHURN_ALERT | HIGH_RISK
        risk_level    (str)  : Normal | Caution | High
    """
    t = (text or "").strip()

    # 발화 없음 → HCX 호출 불필요
    if not t:
        return {
            "skip_hcx": True,
            "churn_signal": 0,
            "type": "NORMAL",
            "mode": "RULE",
            "risk_level": "Normal",
        }

    # 고위험 키워드
    if any(k in t for k in _HIGH_RISK_KEYWORDS):
        return {
            "skip_hcx": False,
            "churn_signal": 1,
            "type": "HIGH_RISK",
            "mode": "RULE",
            "risk_level": "High",
        }

    # 부정/회피 키워드
    if any(k in t for k in _NEG_KEYWORDS):
        return {
            "skip_hcx": False,
            "churn_signal": 1,
            "type": "CHURN_ALERT",
            "mode": "RULE",
            "risk_level": "Caution",
        }

    return {
        "skip_hcx": False,
        "churn_signal": 0,
        "type": "NORMAL",
        "mode": "RULE",
        "risk_level": "Normal",
    }


# =============================================================
# 5. HCX 클라이언트
# =============================================================

def _call_hcx(
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 900,
) -> Optional[str]:
    """
    HyperCLOVA X API를 호출하고 응답 content를 반환한다.
    실패 시 RuntimeError를 발생시킨다.
    """
    url = HCXConfig.endpoint()
    headers = {
        "Authorization": HCXConfig.auth_header(),
        "X-NCP-CLOVASTUDIO-REQUEST-ID": HCXConfig.request_id,
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {
        "messages": messages,
        "temperature": temperature,
        "maxTokens": max_tokens,
    }

    res = requests.post(url, headers=headers, json=payload, timeout=HCXConfig.timeout)

    if not res.ok:
        raise RuntimeError(
            f"HCX HTTP 오류: {res.status_code} — {res.content.decode('utf-8', errors='replace')[:200]}"
        )

    # Windows/PowerShell 환경 한글 깨짐 방지 — bytes 기반 파싱
    data = json.loads(res.content.decode("utf-8"))

    # v3 응답 구조 우선
    try:
        return data["result"]["message"]["content"]
    except (KeyError, TypeError):
        pass

    # OpenAI 호환 fallback
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, TypeError, IndexError):
        return None


# =============================================================
# 6. JSON 파싱 & 검증 유틸
# =============================================================

def _extract_json(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    HCX 응답 문자열에서 JSON 객체를 추출한다.
    마크다운 코드펜스(```json ... ```)도 처리한다.
    """
    if not raw:
        return None

    text = str(raw).strip()
    text = re.sub(r"```[a-zA-Z]*", "", text).replace("```", "").strip()

    # 전체 파싱 시도
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 중괄호 범위 추출
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    # 마지막 } 까지만 파싱
    try:
        last_brace = text.rfind("}")
        if last_brace > 0:
            return json.loads(text[: last_brace + 1])
    except json.JSONDecodeError:
        pass

    return None


def _valid_reply_candidates(cands: Any) -> bool:
    if not isinstance(cands, list) or len(cands) != 3:
        return False
    for c in cands:
        if not isinstance(c, dict):
            return False
        txt = c.get("text")
        why = c.get("why")
        if not isinstance(txt, str) or len(txt.strip()) < 8:
            return False
        if not isinstance(why, str) or len(why.strip()) == 0:
            return False
        # 클릭 삽입용인데 지침형 문장이 섞이면 품질이 급락하므로 실패 처리(재시도 유도)
        if _FORBIDDEN_DIRECTIVE_RE.search(txt):
            return False
    return True


def _is_valid(obj: Any) -> bool:
    """
    필수 키와 타입을 검증한다.
    emotions는 2개 이상 강제.
    suggestions는 3개 리스트 강제.
    reply_candidates는 3개 리스트 강제 + 금지패턴 검사.
    """
    if not isinstance(obj, dict):
        return False

    for key in ("insight", "emotions", "intent", "risk", "suggestions", "reply_candidates"):
        if key not in obj:
            return False

    if not isinstance(obj["insight"], str) or len(obj["insight"].strip()) == 0:
        return False

    if not isinstance(obj["intent"], str) or len(obj["intent"].strip()) == 0:
        return False

    if not isinstance(obj["emotions"], list) or len(obj["emotions"]) < 2:
        return False
    if not all(isinstance(x, str) and x.strip() for x in obj["emotions"][:2]):
        return False

    risk = obj.get("risk")
    if not isinstance(risk, dict):
        return False
    if risk.get("level") not in ("Normal", "Caution", "High"):
        return False
    if "signals" not in risk or not isinstance(risk["signals"], list):
        return False
    if "message" not in risk or not isinstance(risk["message"], str):
        return False

    suggestions = obj.get("suggestions")
    if not isinstance(suggestions, list) or len(suggestions) != 3:
        return False
    for s in suggestions:
        if not isinstance(s, dict):
            return False
        for k in ("type", "rationale", "direction"):
            if k not in s or not isinstance(s[k], str) or len(s[k].strip()) == 0:
                return False

    if not _valid_reply_candidates(obj.get("reply_candidates")):
        return False

    return True


# =============================================================
# 7. 서비스 레이어 — HCX 분석 오케스트레이션
# =============================================================

def _build_history_block(history: Optional[List[Dict[str, str]]]) -> str:
    """
    history에서 최근 HCX_HISTORY_WINDOW개 발화만 추출하여
    '[상담사] ...' / '[내담자] ...' 형식의 문자열로 변환한다.
    """
    if not history:
        return "(없음)"

    window = history[-HCXConfig.history_window :]
    lines = []
    for h in window:
        role = h.get("role")
        prefix = "[상담사]" if role == "counselor" else "[내담자]"
        lines.append(prefix + " " + (h.get("text", "").strip()))
    return "\n".join([x for x in lines if x.strip()]) if lines else "(없음)"


def analyze_with_hcx(
    client_text: str,
    history: Optional[List[Dict[str, str]]] = None,
    last_counselor_text: str = "",
) -> Optional[Dict[str, Any]]:
    """
    내담자 발화와 최근 대화 내역(슬라이딩 윈도우) + 직전 상담사 발화를 HCX에 전달하고 결과를 반환한다.
    1차 시도 실패 시 temperature=0.0으로 1회 재시도한다.
    두 번 모두 실패하면 None을 반환한다.
    """
    history_block = _build_history_block(history)
    counselor_block = (last_counselor_text or "").strip() or "(없음)"

    user_content = (
        f"[이전 대화]\n{history_block}\n\n"
        f"[직전 상담사 발화]\n{counselor_block}\n\n"
        f"[현재 내담자 발화]\n{client_text.strip()}"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    for attempt, temperature in enumerate([0.2, 0.0], start=1):
        if attempt == 2:
            time.sleep(0.15)

        try:
            raw = _call_hcx(messages, temperature=temperature)
        except RuntimeError as e:
            print(f"[HCX {attempt}차 호출 오류] {e}")
            continue

        obj = _extract_json(raw)
        if obj and _is_valid(obj):
            return obj

        # 디버그(필요 시)
        print(f"[HCX {attempt}차 응답 원문] {repr(raw)}")
        print(f"[HCX {attempt}차 파싱 결과] {obj}")
        print(f"[HCX {attempt}차 검증 실패]")

    return None


# =============================================================
# 8. Fallback/Rule-only 응답 생성 (스키마 통일)
# =============================================================

def _pack_response(
    *,
    mode: str,
    churn_signal: int,
    type_: str,
    insight: str,
    emotions: List[str],
    intent: str,
    risk_level: str,
    risk_signals: List[str],
    risk_message: str,
    suggestions: List[Dict[str, str]],
    reply_candidates: List[Dict[str, str]],
) -> Dict[str, Any]:
    return {
        "mode": mode,
        "churn_signal": churn_signal,
        "type": type_,
        "insight": insight,
        "emotions": emotions,
        "intent": intent,
        "risk": {
            "level": risk_level,
            "signals": risk_signals,
            "message": risk_message,
        },
        "suggestions": suggestions,
        "reply_candidates": reply_candidates,
    }


def _fallback(reason: str = "") -> Dict[str, Any]:
    """HCX 분석 실패 시 반환할 기본 응답(스키마 유지)"""
    suggestions = [
        {"type": "공감 심화", "rationale": "AI 분석 실패", "direction": "내담자 감정 반영을 우선하고 부담 지점을 가볍게 탐색"},
        {"type": "탐색", "rationale": "AI 분석 실패", "direction": "핵심 주제(업무/관계/생활) 중 영향이 큰 영역을 먼저 확인"},
        {"type": "목표/다음단계", "rationale": "AI 분석 실패", "direction": "이번 대화에서 얻고 싶은 것 1가지를 합의하고 작게 진행"},
    ]
    reply_candidates = _make_rule_reply_candidates("", "Normal")

    return _pack_response(
        mode="FALLBACK",
        churn_signal=0,
        type_="NORMAL",
        insight=f"AI 분석 지연: {reason}" if reason else "AI 분석 지연",
        emotions=["불명확", "파악불가"],
        intent="대화 진행 중",
        risk_level="Normal",
        risk_signals=[],
        risk_message="현재 상태 정상. 상담을 이어가세요.",
        suggestions=suggestions,
        reply_candidates=reply_candidates,
    )


def _rule_only_response(client_text: str, risk_level: str) -> Dict[str, Any]:
    churn_signal = 1 if risk_level in ("Caution", "High") else 0
    type_ = "HIGH_RISK" if risk_level == "High" else ("CHURN_ALERT" if risk_level == "Caution" else "NORMAL")

    suggestions = _make_rule_suggestions(client_text, risk_level)
    reply_candidates = _make_rule_reply_candidates(client_text, risk_level)

    # 최소한의 insight/emotions/intent는 규칙 기반으로 채움
    if risk_level == "High":
        insight = "고위험 신호가 감지되어 안전 확인이 우선 필요합니다."
        emotions = ["절망", "불안"]
        intent = "고통 완화 또는 도움 요청 가능성(단정 금지)"
        risk_signals = ["고위험 키워드 포함"]
        risk_message = "즉시 안전 확인 개입이 필요합니다. 위험도 평가(사고/계획/수단)와 보호 자원 점검을 우선하세요."
    elif risk_level == "Caution":
        insight = "부정/회피 신호가 감지되어 상담 동기/부담 요인을 탐색할 필요가 있습니다."
        emotions = ["피로", "무기력"]
        intent = "부담 완화/기대 조정 욕구 가능성(단정 금지)"
        risk_signals = ["부정/회피 키워드 포함"]
        risk_message = "이탈로 단정하지 말고, 부담/기대/저항 지점을 안전하게 확인하세요."
    else:
        insight = "현재 발화만으로는 큰 위험 신호 없이 정서·상황 탐색을 이어가면 좋습니다."
        emotions = ["복합감정", "긴장"]
        intent = "이해받고 싶은 욕구 또는 정리 욕구 가능성(단정 금지)"
        risk_signals = []
        risk_message = "정상 범주. 흐름을 유지하며 구체 맥락을 확인하세요."

    return _pack_response(
        mode="RULE_ONLY",
        churn_signal=churn_signal,
        type_=type_,
        insight=insight,
        emotions=emotions,
        intent=intent,
        risk_level=risk_level,
        risk_signals=risk_signals,
        risk_message=risk_message,
        suggestions=suggestions,
        reply_candidates=reply_candidates,
    )


# =============================================================
# 9. FastAPI 라우터
# =============================================================

router = APIRouter(prefix="/helper", tags=["helper"])


@router.post("/suggestion")
def helper_suggestion(payload: HelperRequest) -> Dict[str, Any]:
    """
    내담자의 최근 발화를 분석하여 상담사에게
    1) 읽기용 분석/개입 방향(suggestions)
    2) 클릭 삽입용 응답 초안(reply_candidates)
    을 함께 반환한다.

    흐름:
      1. 룰 기반 1차 필터 (키워드 검사)
      2. USE_HCX=0 이면 RULE_ONLY 반환 (스키마 유지)
      3. USE_HCX=1 이면 HCX 분석 → 실패 시 FALLBACK (스키마 유지)
      4. 룰/HCX 위험 수준 중 높은 쪽을 반영
    """
    client_text = (payload.last_client_text or "").strip()
    last_counselor_text = (payload.last_counselor_text or "").strip()

    rule = rule_check(client_text)

    # HCX 비활성화 모드 (개발/테스트)
    if not HCXConfig.use_hcx:
        # 발화 없음 포함하여 스키마 통일
        return _rule_only_response(client_text, rule.get("risk_level", "Normal"))

    # 발화 없음 등 → HCX 호출 불필요: 스키마 통일해서 반환
    if rule.get("skip_hcx"):
        return _rule_only_response(client_text, "Normal")

    # HCX 분석 실행
    try:
        obj = analyze_with_hcx(
            client_text=client_text,
            history=payload.history,
            last_counselor_text=last_counselor_text,
        )
    except Exception as e:
        return _fallback(str(e))

    if obj is None:
        # 룰 기반 위험 수준을 반영한 RULE_ONLY로라도 안정적인 클릭 문장 제공
        return _rule_only_response(client_text, rule.get("risk_level", "Normal"))

    # 위험 수준 통합 (룰 기반 신호와 HCX 신호 중 높은 쪽 적용)
    hcx_level = (obj.get("risk", {}) or {}).get("level", "Normal")
    rule_level = rule.get("risk_level", "Normal")

    def _rank(level: str) -> int:
        return {"Normal": 0, "Caution": 1, "High": 2}.get(level, 0)

    final_level = hcx_level if _rank(hcx_level) >= _rank(rule_level) else rule_level

    churn_signal = 1 if final_level in ("Caution", "High") else 0
    type_ = "HIGH_RISK" if final_level == "High" else ("CHURN_ALERT" if churn_signal else "NORMAL")

    # HCX 결과가 final_level보다 낮게 나왔는데 룰이 더 높이면,
    # reply_candidates/suggestions는 룰 기반으로 안전하게 덮어쓰는 쪽이 안정적
    if _rank(rule_level) > _rank(hcx_level):
        suggestions = _make_rule_suggestions(client_text, final_level)
        reply_candidates = _make_rule_reply_candidates(client_text, final_level)
        insight = "룰 기반 신호가 우선되어 안전/이탈 관련 탐색을 강화합니다."
        emotions = obj.get("emotions", ["불명확", "파악불가"])
        intent = obj.get("intent", "대화 진행 중")
        risk = obj.get("risk", {}) or {}
        risk_signals = list(set((risk.get("signals") or []) + ["룰 기반 키워드 신호"]))
        risk_message = risk.get("message") or "룰 기반 신호가 있어 주의 깊은 확인이 필요합니다."

        return _pack_response(
            mode="HCX+RULE",
            churn_signal=churn_signal,
            type_=type_,
            insight=insight,
            emotions=emotions,
            intent=intent,
            risk_level=final_level,
            risk_signals=risk_signals,
            risk_message=risk_message,
            suggestions=suggestions,
            reply_candidates=reply_candidates,
        )

    # 일반 HCX 결과 반환
    return _pack_response(
        mode="HCX",
        churn_signal=churn_signal,
        type_=type_,
        insight=obj.get("insight", ""),
        emotions=obj.get("emotions", []),
        intent=obj.get("intent", ""),
        risk_level=final_level,
        risk_signals=(obj.get("risk", {}) or {}).get("signals", []),
        risk_message=(obj.get("risk", {}) or {}).get("message", ""),
        suggestions=obj.get("suggestions", []),
        reply_candidates=obj.get("reply_candidates", []),
    )