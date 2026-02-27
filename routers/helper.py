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
# 시스템 프롬프트
# =========================================================
SYSTEM_PROMPT = (
    "너는 심리상담사의 의사결정을 실시간으로 보조하는 AI 헬퍼다."
    " 너는 상담사 대신 말하거나 내담자에게 직접 답하지 않는다."
    " 너는 상담사가 다음 개입을 결정할 수 있도록 분석 정보를 제공한다."
    " [절대 규칙: 앵무새 화법 및 기계적 안부 금지]"
    " 1. 내담자의 발화를 거울처럼 똑같이 따라 하거나 단순 반복하는 기계적인 공감을 절대 금지한다."
    " 2. 내담자가 이미 자신의 피곤함, 스트레스 원인, 현재 상황 등을 밝혔을 경우, '요즘 어떻게 지내시나요?'나 '많이 힘드시군요' 같은 1차원적이고 대화 흐름을 끊는 템플릿형 기본 안부 인사를 절대 사용하지 마라."
    " 3. 표면적인 공감을 넘어 내담자의 구체적인 상황에 맞춘 깊이 있는 탐색 질문(예: '최근에 잠은 좀 푹 주무셨나요?', '그 상황에서 어떤 부분이 가장 지치게 하나요?')을 제안하라."
    " [절대 규칙: 포맷 및 제안 개수]"
    " 4. 출력은 반드시 JSON 한 줄만 보낼 것. 설명/마크다운 금지."
    " 5. suggestions 리스트는 반드시 정확히 3개의 선택지를 제공해야 한다. 1개나 2개가 아닌 무조건 3개다."
    " 6. suggestions 리스트의 'direction' 필드에는 상담사가 내담자에게 '직접 전송할 수 있는 자연스러운 답변 및 질문 문장'을 1~2문장으로 작성하라."
    " 7. (~해보세요, ~하십시오) 같은 상담사 대상 지침은 절대 direction에 넣지 마라."
    " JSON은 반드시 파싱 가능해야 한다."
    " 필수 키: insight, emotions, intent, risk, suggestions"
    " emotions는 문자열 리스트로 작성하되, 파악이 어렵거나 단순 인사인 경우 빈 리스트([])로 두어라."
    " risk.level은 Normal 또는 Caution 또는 High 중 하나."
    " suggestions는 반드시 길이 3의 리스트, 각 원소는 {type, rationale, direction} 형태."
    " 진단/처방/의학적 단정 금지."
    " [안전 규칙]"
    " 자해/자살/타해/학대/응급 징후가 있으면 risk.level=High."
    " High일 때는 안전 확인 개입이 필요함을 risk.message에 안내."
    " [suggestions 규칙]"
    " type: 개입 유형(공감 심화/상황 탐색/구체적 질문/위험 모니터링 등)."
    " rationale: 이 개입이 필요한 구체적인 근거."
    " direction: 앵무새 화법을 피한, 내담자에게 직접 건넬 구체적이고 자연스러운 대화 문장."
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

JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

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
        "insight": "AI 분석 지연: " + reason,
        "emotions": ["확인중"],
        "intent": "대화 진행중",
        "risk": {
            "level": "Normal",
            "signals": [],
            "message": "현재 상태 정상. 상담을 이어가세요."
        },
        "suggestions": [
            {"type": "대화 유도", "rationale": "기본 응답", "direction": "네, 편하게 계속 말씀해 주세요."},
            {"type": "상태 탐색", "rationale": "기본 응답", "direction": "지금 가장 신경 쓰이는 부분은 무엇인가요?"},
            {"type": "감정 확인", "rationale": "기본 응답", "direction": "그 일로 인해 마음이 어떠신지 조금 더 이야기해 주실 수 있나요?"}
        ],
        "type": "NORMAL"
    }

def safe_json_extract(text):
    if text is None:
        return None
    text_str = str(text).strip()
    text_str = re.sub(r"```[a-zA-Z]*", "", text_str)
    text_str = text_str.replace("```", "").strip()

    try:
        return json.loads(text_str)
    except Exception:
        pass

    m = re.search(r"\{[\s\S]*\}", text_str)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None

# [핵심 수정]: 빈 리스트([])를 허용하도록 검증 로직 완화
def check_completeness(obj) -> bool:
    if not isinstance(obj, dict):
        return False
    for k in ["insight", "emotions", "intent", "risk", "suggestions"]:
        if k not in obj:
            return False
            
    # 감정이 비어있어도 통과시키도록 len 조건 삭제
    if not isinstance(obj.get("emotions"), list):
        return False
        
    risk = obj.get("risk", {})
    if not isinstance(risk, dict):
        return False
    if risk.get("level") not in ["Normal", "Caution", "High"]:
        return False
        
    # 제안이 비어있어도 에러내지 않음
    sugg = obj.get("suggestions")
    if not isinstance(sugg, list):
        return False
    for s in sugg:
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
# HCX 호출 및 재시도 로직
# =========================================================
def call_hcx(messages: List[Dict[str, str]],
             temperature: float = 0.2,
             max_tokens: int = 2000) -> Optional[str]:
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

    res = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if not res.ok:
        raise RuntimeError("HCX HTTP 실패: " + str(res.status_code))

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

def analyze_with_hcx(client_text: str,
                     history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    history_block = ""
    if history:
        history_block = "\n".join(
            [("[상담사]" if h.get("role") == "counselor" else "[내담자]") + " " + h.get("text", "")
             for h in history[-4:]]
        )

    user_content = "[이전 대화]\n" + (history_block or "(없음)") + "\n\n[현재 내담자 발화]\n" + client_text.strip()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_content}]

    # 1차 시도
    content = call_hcx(messages, temperature=0.2, max_tokens=2000)
    
    # [수정] 터미널에서 글자가 잘려보이는 오해를 막기 위해 [:300] 제한 삭제
    print(f"[HCX 1차 응답] {repr(content)}")
    obj = safe_json_extract(content)
    
    completeness = check_completeness(obj) if obj else False
    print(f"[HCX 1차 파싱 성공여부] {obj is not None}, 검증통과여부={completeness}")
    if obj and completeness:
        return obj

    time.sleep(0.15)

    # 2차 재시도
    content = call_hcx(messages, temperature=0.0, max_tokens=2000)
    print(f"[HCX 2차 응답] {repr(content)}")
    obj = safe_json_extract(content)
    
    completeness = check_completeness(obj) if obj else False
    print(f"[HCX 2차 파싱 성공여부] {obj is not None}, 검증통과여부={completeness}")
    if obj and completeness:
        return obj

    return None

# =========================================================
# 엔드포인트
# =========================================================
@router.post("/suggestion")
def helper_suggestion(payload: HelperRequest):
    text = (payload.last_client_text or "").strip()
    rule = rule_check(text)
    if rule.get("skip_hcx"): return rule

    use_hcx = _env("USE_HCX", "0") == "1"
    if not use_hcx:
        rule["mode"] = "RULE_ONLY"
        return rule

    try:
        obj = analyze_with_hcx(text, payload.history)
        if obj is None:
            # [수정] JSON 파싱이 아니라 내용 검증에서 떨어졌음을 명확히 안내
            result = _fallback_result("AI 응답 내용 부족 (단순 인사 등)")
        else:
            risk_level = obj.get("risk", {}).get("level", "Normal")
            churn = 1 if risk_level in ("Caution", "High") else 0
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