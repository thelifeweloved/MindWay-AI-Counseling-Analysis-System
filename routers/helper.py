"""
helper.py — MindWay AI 헬퍼 모듈 (전체 재설계)
================================================
역할  : 상담사 채팅 화면에서 내담자의 최근 발화(슬라이딩 윈도우)를
        분석하여 상담사의 판단을 돕는 참고 정보와 응답 후보 3개를 제공한다.
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
from typing import Any, Dict, List, Optional

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
    model:      str  = os.getenv("HCX_MODEL",           "HCX-DASH-002").strip()
    api_key:    str  = os.getenv("HCX_API_KEY",         "").strip()
    request_id: str  = os.getenv("HCX_REQUEST_ID",      "mindway-helper").strip()
    timeout:    int  = int(os.getenv("HCX_TIMEOUT",     "20") or "20")
    version:    str  = os.getenv("HCX_API_VERSION",     "v3").strip()   # .env 값 활용
    use_hcx:    bool = os.getenv("USE_HCX",             "0").strip() == "1"

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
            raise RuntimeError(
                "HCX_API_KEY가 비어 있습니다. .env 파일을 확인하세요."
            )
        if key.lower().startswith("bearer "):
            return key
        return f"Bearer {key}"


# =============================================================
# 2. 시스템 프롬프트
# =============================================================

SYSTEM_PROMPT = (
    "너는 심리상담사의 의사결정을 실시간으로 보조하는 AI 헬퍼다."
    " 너는 상담사 대신 말하거나 내담자에게 직접 답하지 않는다."
    " 너는 상담사가 다음 개입을 결정할 수 있도록 분석 정보를 제공한다."

    " [절대 규칙: 앵무새 화법 및 기계적 안부 금지]"
    " 1. 내담자의 발화를 거울처럼 따라 하거나 단순 반복하는 기계적 공감을 절대 금지한다."
    " 2. 내담자가 이미 피곤함·스트레스 원인·현재 상황을 밝혔을 경우,"
    " '요즘 어떻게 지내시나요?'나 '많이 힘드시군요' 같은 템플릿형 안부를 절대 사용하지 마라."
    " 3. 표면적 공감을 넘어 내담자의 구체적 상황에 맞춘 깊이 있는 탐색 질문을 제안하라."

    " [절대 규칙: 포맷 및 제안 개수]"
    " 4. 출력은 반드시 JSON 한 줄만 보낼 것. 설명/마크다운 금지."
    " 5. suggestions 리스트는 반드시 정확히 3개의 선택지를 제공해야 한다."
    " 6. suggestions의 'direction' 필드에는 상담사가 내담자에게 직접 전송할 수 있는"
    " 자연스러운 답변·질문 문장을 1~2문장으로 작성하라."
    " 7. (~해보세요, ~하십시오) 같은 상담사 대상 지침은 direction에 절대 넣지 마라."

    " [응답 JSON 스키마]"
    " {"
    "   insight: string,"
    "   emotions: string[],"
    "   intent: string,"
    "   risk: { level: 'Normal'|'Caution'|'High', signals: string[], message: string },"
    "   suggestions: [{ type: string, rationale: string, direction: string }, ...]"
    " }"
    " emotions는 파악이 어렵거나 단순 인사인 경우 빈 배열([])로 둔다."
    " risk.level은 Normal·Caution·High 중 하나만 사용한다."
    " suggestions는 길이 3 고정. 진단·처방·의학적 단정 금지."

    " [안전 규칙]"
    " 자해·자살·타해·학대·응급 징후 탐지 시 risk.level=High로 설정한다."
    " High일 때는 risk.message에 안전 확인 개입 필요 안내를 포함한다."
    " 확신 없으면 risk.level=Caution으로 설정하고 나머지 필드는 최대한 채운다."
)


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
        last_counselor_text : 상담사의 직전 발화 (선택)
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

_NEG_KEYWORDS: tuple = (
    "그만", "포기", "싫어", "힘들", "못하겠",
    "안 할래", "의미없", "죽고싶",
)
_HIGH_RISK_KEYWORDS: tuple = (
    "죽고싶", "자해", "사라지고싶", "없어지고싶", "끝내고싶",
)


def rule_check(text: str) -> Dict[str, Any]:
    """
    발화를 키워드 기반으로 1차 분류한다.

    Returns dict with keys:
        skip_hcx    (bool) : True이면 HCX 호출 없이 바로 반환
        churn_signal (int) : 이탈/위험 신호 여부 (0 or 1)
        type         (str) : NORMAL | CHURN_ALERT | HIGH_RISK
        risk_level   (str) : Normal | Caution | High
    """
    t = (text or "").strip()

    # 발화 없음 → HCX 호출 불필요
    if not t:
        return {
            "skip_hcx":     True,
            "churn_signal": 0,
            "type":         "NORMAL",
            "mode":         "RULE",
            "insight":      "발화 없음",
            "risk_level":   "Normal",
            "suggestion":   "내담자 발화가 없습니다. 라포 형성부터 시작하세요.",
        }

    # 고위험 키워드
    if any(k in t for k in _HIGH_RISK_KEYWORDS):
        return {
            "skip_hcx":     False,
            "churn_signal": 1,
            "type":         "HIGH_RISK",
            "mode":         "RULE",
            "risk_level":   "High",
        }

    # 부정 키워드
    if any(k in t for k in _NEG_KEYWORDS):
        return {
            "skip_hcx":     False,
            "churn_signal": 1,
            "type":         "CHURN_ALERT",
            "mode":         "RULE",
            "risk_level":   "Caution",
        }

    return {
        "skip_hcx":     False,
        "churn_signal": 0,
        "type":         "NORMAL",
        "mode":         "RULE",
        "risk_level":   "Normal",
    }


# =============================================================
# 5. HCX 클라이언트
# =============================================================

def _call_hcx(
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 2000,
) -> Optional[str]:
    """
    HyperCLOVA X API를 호출하고 응답 content를 반환한다.
    실패 시 RuntimeError를 발생시킨다.
    """
    url     = HCXConfig.endpoint()
    headers = {
        "Authorization":                 HCXConfig.auth_header(),
        "X-NCP-CLOVASTUDIO-REQUEST-ID":  HCXConfig.request_id,
        "Content-Type":                  "application/json; charset=utf-8",
    }
    payload = {
        "messages":    messages,
        "temperature": temperature,
        "maxTokens":   max_tokens,
    }

    res = requests.post(url, headers=headers, json=payload, timeout=HCXConfig.timeout)
    res.encoding = "utf-8"  # 한글 깨짐 방지

    if not res.ok:
        raise RuntimeError(
            f"HCX HTTP 오류: {res.status_code} — {res.text[:200]}"
        )

    data    = res.json()
    content = None

    # v3 응답 구조 우선 탐색
    try:
        content = data["result"]["message"]["content"]
    except (KeyError, TypeError):
        pass

    # OpenAI 호환 구조 fallback
    if content is None:
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, TypeError, IndexError):
            pass

    return content


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

    text = re.sub(r"```[a-zA-Z]*", "", str(raw)).replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _is_valid(obj: Any) -> bool:
    """
    필수 키와 타입을 검증한다.
    emotions 빈 리스트, suggestions 빈 리스트는 통과 허용한다.
    """
    if not isinstance(obj, dict):
        return False

    for key in ("insight", "emotions", "intent", "risk", "suggestions"):
        if key not in obj:
            return False

    if not isinstance(obj["emotions"], list):
        return False

    risk = obj.get("risk", {})
    if not isinstance(risk, dict):
        return False
    if risk.get("level") not in ("Normal", "Caution", "High"):
        return False

    suggestions = obj.get("suggestions")
    if not isinstance(suggestions, list):
        return False
    for s in suggestions:
        if not isinstance(s, dict) or "type" not in s:
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

    window = history[-HCXConfig.history_window:]
    lines  = [
        ("[상담사]" if h.get("role") == "counselor" else "[내담자]")
        + " "
        + h.get("text", "").strip()
        for h in window
    ]
    return "\n".join(lines) if lines else "(없음)"


def analyze_with_hcx(
    client_text: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    내담자 발화와 최근 대화 내역을 HCX에 전달하고 분석 결과를 반환한다.
    1차 시도 실패 시 temperature=0.0으로 1회 재시도한다.
    두 번 모두 실패하면 None을 반환한다.
    """
    history_block = _build_history_block(history)
    user_content  = (
        f"[이전 대화]\n{history_block}\n\n"
        f"[현재 내담자 발화]\n{client_text.strip()}"
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_content},
    ]

    for attempt, temperature in enumerate([0.2, 0.0], start=1):
        if attempt == 2:
            time.sleep(0.15)  # 재시도 전 짧은 대기

        try:
            raw = _call_hcx(messages, temperature=temperature)
        except RuntimeError as e:
            print(f"[HCX {attempt}차 호출 오류] {e}")
            continue

        print(f"[HCX {attempt}차 응답] {repr(raw)}")

        obj   = _extract_json(raw)
        valid = _is_valid(obj) if obj else False

        print(f"[HCX {attempt}차] 파싱={obj is not None}, 검증={valid}")

        if obj and valid:
            return obj

    return None


# =============================================================
# 8. Fallback 응답 생성
# =============================================================

def _fallback(reason: str = "") -> Dict[str, Any]:
    """HCX 분석 실패 시 반환할 기본 응답"""
    return {
        "mode":         "FALLBACK",
        "churn_signal": 0,
        "insight":      f"AI 분석 지연: {reason}" if reason else "AI 분석 지연",
        "emotions":     [],
        "intent":       "대화 진행 중",
        "risk": {
            "level":   "Normal",
            "signals": [],
            "message": "현재 상태 정상. 상담을 이어가세요.",
        },
        "suggestions": [
            {
                "type":      "대화 유도",
                "rationale": "기본 응답",
                "direction": "네, 편하게 계속 말씀해 주세요.",
            },
            {
                "type":      "상태 탐색",
                "rationale": "기본 응답",
                "direction": "지금 가장 신경 쓰이는 부분은 무엇인가요?",
            },
            {
                "type":      "감정 확인",
                "rationale": "기본 응답",
                "direction": "그 일로 인해 마음이 어떠신지 조금 더 이야기해 주실 수 있나요?",
            },
        ],
        "type": "NORMAL",
    }


# =============================================================
# 9. FastAPI 라우터
# =============================================================

router = APIRouter(prefix="/helper", tags=["helper"])


@router.post("/suggestion")
def helper_suggestion(payload: HelperRequest) -> Dict[str, Any]:
    """
    내담자의 최근 발화를 분석하여 상담사에게 개입 제안 3개를 반환한다.

    흐름:
      1. 룰 기반 1차 필터 (키워드 검사)
      2. USE_HCX=0 이면 룰 결과만 반환 (개발/테스트 모드)
      3. USE_HCX=1 이면 HCX 분석 → 실패 시 Fallback
    """
    text = (payload.last_client_text or "").strip()
    rule = rule_check(text)

    # 발화 없음 등 HCX 호출이 불필요한 경우
    if rule.get("skip_hcx"):
        return rule

    # HCX 비활성화 모드 (개발/테스트)
    if not HCXConfig.use_hcx:
        rule["mode"] = "RULE_ONLY"
        return rule

    # HCX 분석 실행
    try:
        obj = analyze_with_hcx(text, payload.history)
    except Exception as e:
        return _fallback(str(e))

    if obj is None:
        return _fallback("AI 응답 내용 부족 (단순 인사 또는 파싱 실패)")

    # 위험 수준 통합 (룰 기반 신호와 HCX 신호 중 높은 쪽 적용)
    risk_level   = obj.get("risk", {}).get("level", "Normal")
    churn_signal = 1 if risk_level in ("Caution", "High") else 0
    churn_signal = max(churn_signal, rule.get("churn_signal", 0))

    return {
        "mode":        "HCX",
        "churn_signal": churn_signal,
        "type":        "CHURN_ALERT" if churn_signal else "NORMAL",
        "insight":     obj.get("insight",     ""),
        "emotions":    obj.get("emotions",    []),
        "intent":      obj.get("intent",      ""),
        "risk":        obj.get("risk",        {}),
        "suggestions": obj.get("suggestions", []),
    }
