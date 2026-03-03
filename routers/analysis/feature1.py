# feature1.py
# 핵심기능1: 이탈/종결(연속성 저하) 신호 감지 -> alert 테이블 저장용 결과 생성
# ✅ action 저장 제거 버전 (DB 컬럼은 존재하더라도 값은 저장하지 않음)

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


ALERT_TYPE = "CONTINUITY_SIGNAL"
STATUS_DETECTED = "DETECTED"
STATUS_RESOLVED = "RESOLVED"


def _clamp01(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
    except Exception:
        return default
    if v < 0:
        return 0.0
    if v > 1:
        return 1.0
    return round(v, 3)


def _extract_json(content: str) -> dict:
    if not isinstance(content, str):
        raise ValueError("content is not string")

    s = content.strip()
    if not s:
        raise ValueError("empty content")

    m = re.search(r"```(?:json)?\s*(.*?)\s*```", s, flags=re.DOTALL | re.IGNORECASE)
    if m:
        s = m.group(1).strip()

    first = s.find("{")
    last = s.rfind("}")
    if first != -1 and last != -1 and last > first:
        return json.loads(s[first:last + 1])

    return json.loads(s)


def _level_from_score(score01: float) -> str:
    s = float(score01)
    if s <= 0.29:
        return "LOW"
    if s <= 0.59:
        return "MID"
    return "HIGH"


# 룰 기반 (action 문구는 내부적으로만 있고 최종 row에는 안 넣음)
_RULES = [
    # 관계 단절 의도 (가장 강한 신호)
    (re.compile(r"(연락(도)?\s*안\s*했으면|연락\s*하지\s*마|다시\s*안\s*오|상담\s*원치\s*않)"), 0.90, "RELATION_CUTOFF"),
    (re.compile(r"(다음\s*상담\s*안|상담\s*(안\s*올|오지\s*않|못\s*올|안\s*와도)|더\s*이상\s*상담)"), 0.90, "RELATION_CUTOFF"),

    # 상담 중단 의도
    (re.compile(r"(상담\s*(그만|못\s*하겠)|더\s*못\s*하겠|그만두고\s*싶)"), 0.80, "QUIT_INTENT"),
    (re.compile(r"(그만\s*하고\s*싶|포기\s*하고\s*싶|포기할\s*것\s*같|그냥\s*포기)"), 0.80, "QUIT_INTENT"),
    (re.compile(r"(상담(이|을)?\s*(의미없|소용없|도움이\s*안|필요없))"), 0.80, "QUIT_INTENT"),
    (re.compile(r"(이제는?\s*그만|상담\s*그만두|계속\s*(하기\s*)?(힘들|싫))"), 0.80, "QUIT_INTENT"),

    # 조기 종료 의도
    (re.compile(r"(오늘은\s*여기까지만|그만\s*할게요|이만\s*끝낼게요)"), 0.60, "EARLY_END"),
    (re.compile(r"(오늘은\s*(이만|여기서)|더\s*이야기\s*(하기\s*)?(싫|힘들|못))"), 0.60, "EARLY_END"),

    # 참여 저하
    (re.compile(r"(너무\s*힘들|지치|피곤|더\s*이야기하기\s*힘들)"), 0.45, "LOW_ENGAGEMENT"),
    (re.compile(r"(말할\s*게\s*없|귀찮|하기\s*싫|상담(이)?\s*부담)"), 0.50, "LOW_ENGAGEMENT"),
    (re.compile(r"(잘\s*모르겠어요|어떻게\s*해야\s*할지\s*모르겠|좋아지지\s*않)"), 0.45, "LOW_ENGAGEMENT"),
    (re.compile(r"(매번\s*(똑같|그대로|변하지\s*않)|달라지는\s*게\s*없)"), 0.50, "LOW_ENGAGEMENT"),

    # 회피/단답
    (re.compile(r"(그냥요|모르겠어요|잘\s*모르겠어요)"), 0.35, "AVOID_SHORT"),
    (re.compile(r"(그냥\s*그래요|별로요|딱히요|그저\s*그래요)"), 0.35, "AVOID_SHORT"),
]


def _rule_detect(text: str) -> Dict[str, Any]:
    txt = (text or "").strip()
    if not txt:
        return {"detected": False, "score": 0.0, "rule": "NONE"}

    best = {"detected": False, "score": 0.0, "rule": "NONE"}

    for pattern, score, rule in _RULES:
        if pattern.search(txt):
            if score > best["score"]:
                best = {"detected": True, "score": score, "rule": rule}

    return best


def _build_prompt_for_single_message(text: str) -> str:
    return f"""
너는 상담 운영 보조용 분석기다.
아래 내담자 발화 1개를 보고 "이탈/종결 신호 강도"를 평가하라.

[점수 정의]
- score는 "신호 강도"이다. (0.00~1.00)

[레벨 구간]
- LOW  : 0.00~0.29
- MID  : 0.30~0.59
- HIGH : 0.60~1.00

[rule 선택]
- RELATION_CUTOFF
- QUIT_INTENT
- EARLY_END
- LOW_ENGAGEMENT
- AVOID_SHORT
- NONE

[출력 규칙]
- 반드시 JSON만 출력
- 키는 정확히 3개만 사용:
  1) detected : boolean
  2) score    : number (0~1)
  3) rule     : string

[입력 발화]
{text}
""".strip()


def _llm_refine_single_message(clova_client, text: str) -> Dict[str, Any]:
    r = clova_client.chat(
        system_text="너는 상담 운영 보조용 이탈신호 분석기다. 반드시 JSON만 출력한다.",
        user_text=_build_prompt_for_single_message(text),
        temperature=0.0,
        timeout=60,
    )
    content = r["result"]["message"]["content"]
    data = _extract_json(content)

    detected = bool(data.get("detected", False))
    score = _clamp01(data.get("score", 0.0), default=0.0)
    rule = str(data.get("rule", "NONE")).strip().upper()

    allowed_rules = {"RELATION_CUTOFF", "QUIT_INTENT", "EARLY_END", "LOW_ENGAGEMENT", "AVOID_SHORT", "NONE"}
    if rule not in allowed_rules:
        rule = "NONE"

    if rule == "NONE":
        detected = False
        score = 0.0

    return {"detected": detected, "score": score, "rule": rule}


def analyze_feature1_for_alert_row(
    clova_client,
    *,
    sess_id: int,
    msg_id: int,
    speaker: str,
    text: str,
    at: Optional[str] = None,
    use_llm: bool = True,
    llm_only_if_rule_hit: bool = True,
    store_low: bool = True,
) -> Optional[Dict[str, Any]]:
    spk = str(speaker or "").upper().strip()
    txt = (text or "").strip()

    if spk != "CLIENT":
        return None
    if not txt:
        return None

    base = _rule_detect(txt)

    result = base
    if use_llm:
        try:
            if (not llm_only_if_rule_hit) or base["detected"]:
                result = _llm_refine_single_message(clova_client, txt)
        except Exception:
            result = base

    score = _clamp01(result.get("score", 0.0), default=0.0)
    detected = bool(result.get("detected", False))
    rule = str(result.get("rule", "NONE")).upper().strip()

    level = _level_from_score(score)

    if (level == "LOW") and (not store_low):
        return None

    # LOW도 저장(요청 흐름 기준)이라면 rule을 LOW로 통일
    if level == "LOW":
        rule = "LOW"
        status = STATUS_DETECTED
    else:
        status = STATUS_DETECTED
        if not detected:
            # 이상치 방어
            rule = "LOW"
            score = min(score, 0.29)

    row = {
        "sess_id": int(sess_id),
        "msg_id": int(msg_id),
        "type": ALERT_TYPE,
        "status": status,
        "score": score,
        "rule": rule,
        # ✅ action 제거
    }
    if at is not None:
        row["at"] = at

    return row


def analyze_feature1_for_alert_rows(
    clova_client,
    *,
    sess_id: int,
    messages: List[Dict[str, Any]],
    use_llm: bool = True,
    llm_only_if_rule_hit: bool = True,  # ✅ 룰에 걸린 것만 LLM 호출 → 호출 횟수 감소
    store_low: bool = False,  # ✅ LOW 저장 안 함 → 불필요한 LLM 호출 감소
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for m in messages:
        row = analyze_feature1_for_alert_row(
            clova_client,
            sess_id=sess_id,
            msg_id=int(m["msg_id"]),
            speaker=str(m.get("speaker", "")),
            text=str(m.get("text", "")),
            at=m.get("at"),
            use_llm=use_llm,
            llm_only_if_rule_hit=llm_only_if_rule_hit,
            store_low=store_low,
        )
        if row:
            rows.append(row)
    return rows


def analyze_feature1(clova_client, dialog_text: str) -> dict:
    base = _rule_detect(dialog_text)
    if not base["detected"]:
        return {"detected": False, "score": 0.0, "rule": "NONE"}
    try:
        return _llm_refine_single_message(clova_client, dialog_text)
    except Exception:
        return base