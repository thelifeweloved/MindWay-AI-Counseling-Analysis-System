# routers/analysis_services/feature4.py

import json
import re
from typing import Any, Dict


def extract_json(content: str) -> dict:
    """
    모델 응답에서 JSON만 안전하게 추출한다.
    - ```json ... ``` 형태
    - 일반 텍스트 안의 { ... } 형태
    """
    # 코드블록 JSON 우선
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, flags=re.DOTALL | re.IGNORECASE)
    if m:
        return json.loads(m.group(1))

    # 일반 문자열에서 첫 { ~ 마지막 } 추출
    first = content.find("{")
    last = content.rfind("}")
    if first != -1 and last != -1 and last > first:
        return json.loads(content[first:last + 1])

    raise ValueError("JSON 파싱 실패")


def clamp_score_0_100(x: Any, default: float = 50.0) -> float:
    """
    점수를 0~100 범위 float로 보정한다.
    DECIMAL(5,2)에 맞게 소수 둘째자리 반올림.
    """
    try:
        v = float(x)
    except Exception:
        v = default

    if v < 0:
        v = 0.0
    elif v > 100:
        v = 100.0

    return round(v, 2)


def build_prompt(dialog_text):
    return f"""
너는 상담 세션 흐름/품질을 평가하는 '엄격한 채점기'이다.
아래 상담 대화를 보고 flow(흐름 점수)와 score(종합 점수)를 평가하라.

[핵심 원칙]
- 관대한 평균 점수(특히 70점대)로 수렴하지 말 것.
- 내담자의 회피/화제전환/짧은 답변 반복이 보이면 flow를 즉시 감점할 것.
- 같은 회피 패턴이 반복되면 누적 감점할 것.
- 단, 상담사가 회피를 잘 다루고 원래 주제로 복귀시키면 score는 일부 방어될 수 있다.

[flow 정의] (0~100)
flow는 '질문-응답 연결성'과 '맥락 유지' 점수이다.
다음 항목을 중심으로 평가하라:
1) 상담사 질문에 내담자가 직접 답하는가?
2) 주제가 유지되는가, 아니면 반복적으로 벗어나는가?
3) 회피성 단답(예: "그냥요", "모르겠어요", "기억 안 나요", "잘 모르겠어요")이 반복되는가?
4) 상담사의 재질문/복귀 시도 후 흐름이 회복되는가?

[score 정의] (0~100)
score는 세션 전반 품질 점수이다.
flow뿐 아니라 상담사의 반응 적절성, 복귀 시도, 탐색 전략, 대화 진행 안정성을 포함한다.

[flow 채점 절차 - 반드시 따를 것]
1) flow 기본점수는 85에서 시작한다.
2) 아래 감점 규칙을 적용한다. (중복 적용 가능)
   - 질문에 직접 답하지 않고 두루뭉술하게 회피: -8
   - 회피성 단답 1회 ("그냥요", "모르겠어요", "기억 안 나요", "잘 모르겠어요" 등): -8
   - 회피성 단답 반복(2회 이상): 추가 발생마다 -6
   - 질문과 무관한 화제전환: -12
   - 상담사 복귀 시도 후에도 계속 회피: -8
   - 대화 진전 거의 없음(반복 회피로 정보 확장 안 됨): -8
3) 아래 보정 규칙을 적용한다.
   - 상담사가 회피를 인정하고 자연스럽게 원주제로 복귀시킴: +4
   - 상담사가 질문 방식을 바꿔 탐색을 시도함: +4
4) 최종 flow는 0~100 범위로 제한한다.

[점수 앵커(참고)]
- flow 80~100: 질문-응답 연결이 좋고 회피가 거의 없음
- flow 65~79: 약한 회피가 있으나 대체로 흐름 유지
- flow 50~64: 회피/단답 반복으로 흐름이 눈에 띄게 흔들림
- flow 35~49: 반복 회피/화제전환으로 흐름 유지가 어려움
- flow 0~34: 맥락 연결이 거의 무너짐

[실제 채점 예시 - 반드시 참고할 것]
예시1 (flow=22):
대화: 상담사가 3번 질문했는데 내담자가 "모르겠어요", "그냥요", "잘 기억 안 나요" 반복
채점: 85 - 8(첫회피) - 6(반복) - 6(반복) - 8(진전없음) - 8(복귀후회피) = 49 → 추가감점 후 22
→ {{"flow": 22, "score": 28, "reason": "3회 연속 회피성 단답으로 대화 진전 없음"}}

예시2 (flow=45):
대화: 회피성 단답 2회, 상담사가 복귀 시도했으나 여전히 단답
채점: 85 - 8 - 6 - 8 - 8 = 55 → 복귀실패로 추가감점 후 45
→ {{"flow": 45, "score": 50, "reason": "회피 2회 반복, 상담사 복귀 시도했으나 효과 제한적"}}

예시3 (flow=85):
대화: 내담자가 질문에 구체적으로 답하고 감정까지 표현, 회피 없음
채점: 85 (감점 없음)
→ {{"flow": 85, "score": 90, "reason": "회피 없이 질문-응답 연결 좋음, 상담사 탐색 우수"}}

[출력 규칙 - 매우 중요]
- 반드시 JSON 객체만 출력할 것 (설명문 금지, 코드블록 금지)
- 키는 정확히 아래 3개만 사용:
  1) flow   : number (0~100)
  2) score  : number (0~100)
  3) reason : string (1~2문장)
- 애매하면 중간값(70점대)으로 뭉개지 말고, 회피 강도에 따라 점수 차이를 분명히 줄 것.

[상담 대화]
{dialog_text}
""".strip()



def analyze_feature4(clova_client, dialog_text: str) -> Dict[str, Any]:
    """
    세션 전체 대화를 기반으로 품질 분석(flow, score)을 수행한다.

    Args:
        clova_client: ClovaXClient 인스턴스 (chat(system_text, user_text, ...) 지원)
        dialog_text: 세션 전체 대화 문자열

    Returns:
        {
          "flow": float,   # 0~100
          "score": float,  # 0~100
          "meta": {
            "reason": str,
            "raw": dict | None
          }
        }

    실패 시에도 fallback 값을 반환하여 서비스 흐름이 끊기지 않게 함.
    """
    text = (dialog_text or "").strip()

    # 대화가 비어 있으면 안전하게 중립값 반환
    if not text:
        return {
            "flow": 50.0,
            "score": 50.0,
            "meta": {
                "reason": "대화 내용이 없어 기본값으로 처리됨",
                "raw": None,
            },
        }

    # 너무 짧은 대화는 신뢰도 낮으므로 중립적 fallback(혹은 모델 호출 가능)
    # 여기서는 모델은 호출하되, 결과가 깨지면 중립값 반환하도록 둠.
    try:
        res = clova_client.chat(
            system_text="너는 상담 세션 품질 평가기다. 반드시 유효한 JSON만 출력한다.",
            user_text=build_prompt(text),
            temperature=0.0,
            timeout=90,
        )
        content = res["result"]["message"]["content"]

        data = extract_json(content)

        flow = clamp_score_0_100(data.get("flow"), default=50.0)
        score = clamp_score_0_100(data.get("score"), default=50.0)
        reason = str(data.get("reason", "")).strip()[:300]

        # 비어 있으면 기본 문구
        if not reason:
            reason = "세션 품질 분석 결과가 생성됨"

        return {
            "flow": flow,
            "score": score,
            "meta": {
                "reason": reason,
                "raw": data,
            },
        }

    except Exception as e:
        # 모델 응답 파싱 실패/네트워크 오류 등 fallback
        return {
            "flow": 50.0,
            "score": 50.0,
            "meta": {
                "reason": f"quality_parse_or_call_error: {type(e).__name__}",
                "raw": None,
            },
        }