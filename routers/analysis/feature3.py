# routers/analysis_services/feature3.py
# 핵심기능3 (감정분석) - A안: 1건씩 분석(가장 안정)
# ✅ runner에서 batch_size=5로 호출해도 에러 안 나게 batch_size 파라미터를 "받기만" 하고 무시함
# DB 저장 최소 결과: msg_id, label, score (+실패 시 meta)

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


ALLOWED_LABELS = {"joy", "sad", "anger", "confusion", "neutral"}
DEFAULT_LABEL = "neutral"
DEFAULT_SCORE = 0.5  # raw score의 기본값(후처리로 라벨 구간에 매핑됨)

# ✅ 사용자가 제안한 "5구간 + 라벨 매핑" (라벨별 score가 항상 해당 구간 안에서 다양하게 나오도록)
# 0.0~0.2, 0.2~0.4, 0.4~0.6, 0.6~0.8, 0.8~1.0
LABEL_BANDS = {
    "neutral": (0.0, 0.2),
    "joy": (0.2, 0.4),
    "sad": (0.4, 0.6),
    "confusion": (0.6, 0.8),
    "anger": (0.8, 1.0),
}


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x).strip()


def _clamp01_raw(x: Any, default: float = DEFAULT_SCORE) -> float:
    """모델이 준 raw score를 0~1로만 정리(라벨 구간 매핑 전 단계)."""
    try:
        v = float(x)
    except Exception:
        return float(default)
    if v < 0:
        v = 0.0
    if v > 1:
        v = 1.0
    return v


def _clamp01_final(x: Any, default: float = DEFAULT_SCORE) -> float:
    """최종 점수(이미 0~1일 것)를 0~1로 보정 + 소수 3자리."""
    try:
        v = float(x)
    except Exception:
        v = float(default)
    if v < 0:
        v = 0.0
    if v > 1:
        v = 1.0
    return round(v, 3)


def _map_score_to_label_band(label: str, score_raw01: float) -> float:
    """
    label이 정한 구간(폭 0.2) 안에서 score가 다양하게 나오도록 재매핑.
    - score_raw01(0~1)을 구간 [low, high]로 선형 변환:
      final = low + score_raw01 * (high - low)
    """
    low, high = LABEL_BANDS.get(label, LABEL_BANDS[DEFAULT_LABEL])
    span = high - low
    # span은 0.2가 기본이지만 혹시 바뀌어도 동작하도록 일반화
    final = low + float(score_raw01) * float(span)
    # anger의 high=1.0 같은 끝값 포함 안정화
    if final > high:
        final = high
    if final < low:
        final = low
    return final


def _extract_json(content: str) -> dict:
    if not isinstance(content, str):
        raise ValueError("feature3: content is not string")

    s = content.strip()
    if not s:
        raise ValueError("feature3: empty content")

    # 코드블록 제거
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", s, flags=re.DOTALL | re.IGNORECASE)
    if m:
        s = m.group(1).strip()

    first = s.find("{")
    last = s.rfind("}")
    if first != -1 and last != -1 and last > first:
        return json.loads(s[first:last + 1])

    return json.loads(s)


def _build_prompt_one(msg_id: int, text: str) -> str:
    """
    ✅ score를 "감정 강도(intensity)"로 정의하고,
    ✅ 5구간 해석 기준 + 라벨별 강도 신호를 제공해서 score 품질/일관성 개선.
    ✅ 출력은 JSON 3키만(파싱 안정성 유지).
    """
    t = _safe_str(text)[:350]

    # 구간 가이드(해석)
    # - 여기서 구간은 "강도" 의미로 설명만 하고, 실제 저장은 라벨별 구간 매핑으로 강제(아래 후처리)
    return f"""
너는 상담 대화에서 내담자(CLIENT) 발화의 감정을 분류하는 감정분석기다.

[라벨(5개) 정의]
- joy: 기쁨/안도/감사/희망/만족
- sad: 슬픔/무기력/상실감/자책/우울
- anger: 분노/짜증/원망/격앙/공격적 비난
- confusion: 혼란/당황/갈피 없음/불확실/결정 어려움
- neutral: 사실 전달 위주/감정 표현 거의 없음

[score 정의 (매우 중요)]
- score는 "선택한 label 감정의 강도(intensity)"를 0~1로 나타낸 값이다.
  - 0.0: 거의 없음(표현 미미)
  - 0.5: 중간(감정이 분명하나 폭발적이진 않음)
  - 1.0: 매우 강함(지배적/폭발적/격앙)

[강도(점수) 구간 해석 가이드]
- 0.0~0.2 : 미미/거의 없음
- 0.2~0.4 : 약함
- 0.4~0.6 : 중간
- 0.6~0.8 : 강함
- 0.8~1.0 : 매우 강함

[강도 판단 체크리스트(출력 금지, 내부 판단용)]
- 강도↑: 느낌표/반복 강조(“진짜 진짜”, “너무 너무”), 단정/비난, 공격적 표현, 극단적 표현(“다 끝났어”), 신체 반응(“숨이 막혀”)
- 강도↓: 완곡(“좀”, “약간”), 추측(“같아”), 정보 전달/설명 위주
- confusion 강도↑: “모르겠어/헷갈려/정리가 안 돼/어떡하지” + 질문 연속
- sad 강도↑: “무기력/눈물/상실/자책/우울”
- anger 강도↑: “짜증/분노/억울/원망/폭발”
- joy 강도↑: “안도/기쁨/감사/희망/설렘”

[출력 규칙]
- 반드시 JSON만 출력 (설명/코드블록/추가 텍스트 금지)
- 키는 정확히 3개만:
  1) msg_id : number
  2) label  : string (joy/sad/anger/confusion/neutral 중 1개)
  3) score  : number (0~1, 소수 가능)

[입력]
{{"msg_id": {int(msg_id)}, "text": {json.dumps(t, ensure_ascii=False)}}}
""".strip()


def analyze_feature3_one(clova_client, *, msg_id: int, text: str) -> Dict[str, Any]:
    """
    1건 분석
    반환: {"msg_id":..., "label":..., "score":...} (+meta optional)
    """
    r = clova_client.chat(
        system_text="너는 감정분석기다. 반드시 JSON만 출력한다. 출력 키는 msg_id,label,score 3개만 허용한다.",
        user_text=_build_prompt_one(int(msg_id), text),
        # ✅ score 다양성(분포) 약간 확보 + 프롬프트 기준으로 일관성 유지
        temperature=0.2,
        timeout=60,
    )
    content = r["result"]["message"]["content"]

    try:
        data = _extract_json(content)

        mid = int(data.get("msg_id", msg_id))

        label = _safe_str(data.get("label", DEFAULT_LABEL)).lower()
        if label not in ALLOWED_LABELS:
            label = DEFAULT_LABEL

        # 모델 raw score (0~1로만 정리)
        score_raw01 = _clamp01_raw(data.get("score", DEFAULT_SCORE), default=DEFAULT_SCORE)

        # ✅ 라벨별 0.2 구간 안으로 재매핑하여 "라벨-구간 정책"을 보장하면서도 다양성 유지
        score_final = _map_score_to_label_band(label, score_raw01)
        score_final = _clamp01_final(score_final, default=DEFAULT_SCORE)

        return {"msg_id": mid, "label": label, "score": score_final}

    except Exception:
        # 파싱 실패 시에도 정책과 유사하게: neutral 구간에 떨어지도록(기본 raw=0.5 → 0.1로 매핑됨)
        fallback_raw = 0.5
        fallback_label = DEFAULT_LABEL
        score_final = _map_score_to_label_band(fallback_label, fallback_raw)
        score_final = _clamp01_final(score_final, default=DEFAULT_SCORE)

        return {
            "msg_id": int(msg_id),
            "label": fallback_label,
            "score": score_final,
            "meta": {"parse_error": True, "raw_preview": content[:300]},
        }


def analyze_feature3(
    clova_client,
    msg_rows: List[Dict[str, Any]],
    *,
    batch_size: Optional[int] = None,  # ✅ runner 호환용(받기만 하고 사용 안 함)
) -> Dict[str, Any]:
    """
    sess_id의 msg_rows를 받아 CLIENT만 1건씩 분석해서 반환

    msg_rows 원소 예:
      {"msg_id":..., "speaker":"CLIENT/COUNSELOR", "text":"..."}

    반환:
      {"items": [ {msg_id,label,score,(meta)} ... ]}
    """
    _ = batch_size  # 명시적으로 무시(호출부 수정 안 해도 됨)

    items: List[Dict[str, Any]] = []

    for m in msg_rows:
        if _safe_str(m.get("speaker", "")).upper() != "CLIENT":
            continue
        txt = _safe_str(m.get("text", ""))
        if not txt:
            continue

        mid = int(m["msg_id"])
        items.append(analyze_feature3_one(clova_client, msg_id=mid, text=txt))

    return {"items": items}