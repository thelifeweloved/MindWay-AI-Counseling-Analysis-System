import os
import json
import re
import time
import requests
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

router = APIRouter(prefix="/helper", tags=["helper"])

# =========================================================
# 시스템 프롬프트 (v2 - 개입 전략 방향 버전)
# =========================================================
SYSTEM_PROMPT = (
    "너는 심리상담사의 의사결정을 실시간으로 보조하는 AI 헬퍼다."
    " 너는 상담사 대신 말하거나 내담자에게 직접 답하지 않는다."
    " 너는 상담사가 다음 개입을 결정할 수 있도록 분석 정보를 제공한다."
    " [절대 규칙]"
    " 출력은 반드시 JSON 한 줄만. 설명/문장/마크다운/코드블록 금지."
    " JSON은 반드시 파싱 가능해야 한다."
    " 필수 키: insight, emotions, intent, risk, suggestions"
    " emotions는 문자열 리스트 3개 이상."
    " risk.level은 Normal 또는 Caution 또는 High 중 하나."
    " suggestions는 길이 3의 리스트,"
    " 각 원소는 {type, rationale, direction} 형태."
    " 진단/처방/의학적 단정 금지."
    " [안전 규칙]"
    " 자해/자살/타해/학대/응급 징후가 있으면 risk.level=High."
    " High일 때는 안전 확인 개입이 필요함을 risk.message에 안내."
    " [suggestions 규칙]"
    " type: 개입 유형(공감 심화/회피 탐색/목표 재확인/위험 모니터링 등)."
    " rationale: 이 개입이 필요한 근거."
    " direction: 상담사가 취할 구체적 전략 방향 1~2문장."
    " [스키마]"
    " {insight: 한문장요약, emotions: [감정1,감정2,감정3],"
    " intent: 욕구추정, risk: {level: Normal|Caution|High,"
    " signals: [근거1], message: 상담사안내},"
    " suggestions: [{type,rationale,direction}x3]}"
    " 확신 없으면 risk.level=Caution으로 하고 나머지는 최대한 채워라."
)

# 룰 기반 키워드
NEG_KEYS = ["그만", "포기", "싫어", "힘들", "못하겠", "안 할래", "의미없", "죽고싶"]
HIGH_RISK_KEYS = ["죽고싶", "자해", "사라지고싶", "없어지고싶", "끝내고싶"]

JSON_RE = re.compile(r"{.*}", re.DOTALL)

# =========================================================
# Request / Response 스키마
# =========================================================
class HelperRequest(BaseModel):
    session_id: int = Field(..., alias="sess_id", ge=1)
    counselor_id: int = Field(..., ge=1)
    last_client_text: str = ""
    last_counselor_text: str = ""
    history: Optional[List[Dict[str, str]]] = None
    context: Optional[Dict[str, Any]] = None

    model_config = {"populate_by_name": True}

# =========================================================
# 유틸
# =========================================================
def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()

def _fallback_result(reason: str = "") -> Dict[str, Any]:
    return {
        "mode": "FALLBACK",
        "churn_signal": 0,
        "insight": "분석 실패: " + reason,
        "emotions": ["불명확", "파악불가", "분석필요"],
        "intent": "추정 불가",
        "risk": {
            "level": "Caution",
            "signals": [],
            "message": "응답 오류. 상담사가 직접 판단 필요"
        },
        "suggestions": [
            {"type": "공감 심화",    "rationale": "분석 실패", "direction": "내담자 감정 반영 탐색 필요"},
            {"type": "탐색",         "rationale": "분석 실패", "direction": "핵심 주제 재확인 질문 고려"},
            {"type": "목표/다음단계","rationale": "분석 실패", "direction": "상담 속도 조율 및 안전 확인"}
        ],
        "type": "NORMAL"
    }

def safe_json_extract(text):
    if text is None:
        return None
    m = JSON_RE.search(str(text).strip())
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None

def check_completeness(obj) -> bool:
    if not isinstance(obj, dict):
        return False
    for k in ["insight", "emotions", "intent", "risk", "suggestions"]:
        if k not in obj:
            return False
    if not isinstance(obj.get("emotions"), list) or len(obj["emotions"]) < 2:
        return False
    risk = obj.get("risk", {})
    if not isinstance(risk, dict):
        return False
    if risk.get("level") not in ["Normal", "Caution", "High"]:
        return False
    sugg = obj.get("suggestions")
    if not isinstance(sugg, list) or len(sugg) < 3:
        return False
    for s in sugg[:3]:
        if not isinstance(s, dict) or "type" not in s:
            return False
    return True

# =========================================================
# 룰 기반 1차 필터
# =========================================================
def rule_check(text: str) -> Dict[str, Any]:
    t = (text or "").strip()
    if not t:
        return {"skip_hcx": True, "churn_signal": 0,
                "type": "NORMAL", "mode": "RULE",
                "insight": "발화 없음",
                "risk_level": "Normal",
                "suggestion": "내담자 발화가 없습니다. 라포 형성부터 시작하세요."}
    if any(k in t for k in HIGH_RISK_KEYS):
        return {"skip_hcx": False, "churn_signal": 1,
                "type": "HIGH_RISK", "mode": "RULE",
                "risk_level": "High"}
    if any(k in t for k in NEG_KEYS):
        return {"skip_hcx": False, "churn_signal": 1,
                "type": "CHURN_ALERT", "mode": "RULE",
                "risk_level": "Caution"}
    return {"skip_hcx": False, "churn_signal": 0,
            "type": "NORMAL", "mode": "RULE",
            "risk_level": "Normal"}

# =========================================================
# HCX 호출 (비스트리밍 JSON 응답)
# =========================================================
def call_hcx(messages: List[Dict[str, str]],
             temperature: float = 0.2,
             max_tokens: int = 300) -> Optional[str]:
    host    = _env("HCX_HOST", "https://clovastudio.stream.ntruss.com")
    model   = _env("HCX_MODEL", "HCX-DASH-002")
    api_key = _env("HCX_API_KEY")
    req_id  = _env("HCX_REQUEST_ID", "mindway-helper")
    timeout = int(_env("HCX_TIMEOUT", "20") or "20")

    if not api_key:
        raise RuntimeError("HCX_API_KEY 가 비어있습니다. .env를 확인하세요.")

    url = f"{host}/v3/chat-completions/{model}"
    headers = {
        "Authorization": api_key,
        "X-NCP-CLOVASTUDIO-REQUEST-ID": req_id,
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {
        "messages": messages,
        "temperature": temperature,
        "maxTokens": max_tokens,
    }

    t0  = time.time()
    res = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if not res.ok:
        raise RuntimeError("HCX HTTP 실패: " + str(res.status_code) + " " + res.text[:200])

    data = res.json()
    content = None
    try:
        content = data["result"]["message"]["content"]
    except Exception:
        pass
    if content is None:
        try:
            content = data["choices"][0]["message"]["content"]
        except Exception:
            pass
    return content

# =========================================================
# HCX 분석 + 재시도
# =========================================================
def analyze_with_hcx(client_text: str,
                     history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    history_block = ""
    if history:
        history_block = "\n".join(
            [("[상담사]" if h.get("role") == "counselor" else "[내담자]") + " " + h.get("text", "")
             for h in history[-4:]]
        )

    user_content = "[이전 대화]\n" + (history_block or "(없음)") + "\n\n[현재 내담자 발화]\n" + client_text.strip()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_content},
    ]

    # 1차 시도
    content = call_hcx(messages, temperature=0.2, max_tokens=300)
    obj = safe_json_extract(content)
    if obj and check_completeness(obj):
        return obj

    time.sleep(0.15)

    # 2차 재시도 (temperature=0 으로 형식 고정)
    content = call_hcx(messages, temperature=0.0, max_tokens=300)
    obj = safe_json_extract(content)
    if obj and check_completeness(obj):
        return obj

    return None

# =========================================================
# 엔드포인트
# =========================================================
@router.post("/suggestion")
def helper_suggestion(payload: HelperRequest):
    text = (payload.last_client_text or "").strip()

    # 1단계: 룰 기반 1차 필터
    rule = rule_check(text)
    if rule.get("skip_hcx"):
        return rule

    use_hcx = _env("USE_HCX", "0") == "1"
    if not use_hcx:
        rule["mode"] = "RULE_ONLY"
        return rule

    # 2단계: HCX 심층 분석
    try:
        obj = analyze_with_hcx(text, payload.history)
        if obj is None:
            result = _fallback_result("JSON 파싱 실패")
        else:
            risk_level = obj.get("risk", {}).get("level", "Normal")
            churn = 1 if risk_level in ("Caution", "High") else 0

            # 룰에서 감지된 churn_signal 이 더 높으면 유지
            churn = max(churn, rule.get("churn_signal", 0))

            result = {
                "mode": "HCX",
                "churn_signal": churn,
                "type": "CHURN_ALERT" if churn else "NORMAL",
                "insight":     obj.get("insight", ""),
                "emotions":    obj.get("emotions", []),
                "intent":      obj.get("intent", ""),
                "risk":        obj.get("risk", {}),
                "suggestions": obj.get("suggestions", []),
            }

    except Exception as e:
        result = _fallback_result(str(e))

    return result