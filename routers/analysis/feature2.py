# feature2.py
# 안정형 핵심기능2:
# - summary는 항상 "텍스트만" (```json/코드블록 제거, JSON이면 summary만 추출)
# - summary 길이 강제(summary_max_len). 길면 한번 더 "압축 요약" 수행
# - 긴 대화는 청크 요약 -> 최종 요약(잘림/파싱 리스크 감소)
# - topic 분류는 선택: topics를 넘기면 topic_id 추천(짧게 1키 JSON만)
# - note는 상담사가 UI에서 작성한 값을 그대로 저장(make_sess_analysis_row)

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


# =========================
# 유틸
# =========================
def _safe_str(x: Any, default: str = "") -> str:
    if x is None:
        return default
    return str(x).strip()


def _truncate(s: str, max_len: int) -> str:
    s = _safe_str(s)
    return s if len(s) <= max_len else s[:max_len].rstrip()


def _strip_code_fence(s: str) -> str:
    s = _safe_str(s)
    if not s:
        return s
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", s, flags=re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else s


def _extract_json_object(content: str) -> dict:
    """
    content에서 JSON 객체만 안전하게 추출
    - ```json ... ``` 대응
    - 앞뒤 텍스트 섞임 대응
    """
    s = _strip_code_fence(content)
    if not s:
        raise ValueError("empty content")

    first, last = s.find("{"), s.rfind("}")
    if first != -1 and last != -1 and last > first:
        return json.loads(s[first:last + 1])

    return json.loads(s)


def clean_summary_for_db(s: str) -> str:
    """
    모델이 ```json { "summary": "..." }``` 혹은 JSON 문자열을 주더라도
    최종적으로 "요약 텍스트만" 반환.
    """
    s = _safe_str(s)
    if not s:
        return ""

    inner = _strip_code_fence(s)

    # JSON 파싱 시도 -> {"summary": "..."}면 값만
    first, last = inner.find("{"), inner.rfind("}")
    if first != -1 and last != -1 and last > first:
        try:
            obj = json.loads(inner[first:last + 1])
            if isinstance(obj, dict) and "summary" in obj:
                return _safe_str(obj["summary"])
        except Exception:
            pass

    # JSON이 아니라면 그대로(그래도 코드펜스는 원본 s에서 제거했으니 inner 사용)
    return _safe_str(inner)


def chunk_text_by_chars(text: str, chunk_size: int = 6000, overlap: int = 400) -> List[str]:
    """
    긴 텍스트를 chunk_size 기준으로 나눔 (overlap으로 문맥 연결)
    """
    text = _safe_str(text)
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


# =========================
# 프롬프트
# =========================
def _prompt_summary_only(dialog_text: str, max_chars: int) -> str:
    return f"""
아래 상담 대화를 바탕으로 상담 요약을 작성하라.

[출력 규칙]
- 반드시 JSON만 출력
- 키는 summary 하나만
- summary는 {max_chars}자 이내 (중요: 반드시 지켜라)
- 반드시 3~4문장 이내로 작성 (절대 초과 금지)
- 핵심 내용만 간결하게, 객관적 요약
- 진단/판정/확정 표현 금지
- 코드블록/마크다운/백틱 사용 금지

[상담 대화]
{dialog_text}
""".strip()


def _prompt_compress(summary_text: str, max_chars: int) -> str:
    return f"""
아래 요약을 {max_chars}자 이내로 더 짧게 압축하라.

[출력 규칙]
- 반드시 JSON만 출력
- 키는 summary 하나만
- summary는 {max_chars}자 이내 (반드시)
- 의미는 유지하되 중복 제거
- 코드블록/마크다운/백틱 사용 금지

[요약]
{summary_text}
""".strip()


def _prompt_topic_only(summary_text: str, topics: List[Dict[str, Any]]) -> str:
    topic_lines = "\n".join([f'- {t["id"]}: {t["name"]} — {t.get("descr","")}' for t in topics])
    return f"""
아래 요약을 보고 대표 토픽을 1개 고르라.

[토픽 후보]
{topic_lines}

[출력 규칙]
- 반드시 JSON만 출력
- 키는 topic_id 하나만
- topic_id는 후보 id 중 하나
- 설명문/코드블록/마크다운 금지

[요약]
{summary_text}
""".strip()


# =========================
# 핵심 로직
# =========================
def summarize_text(
    clova_client,
    dialog_text: str,
    *,
    summary_max_len: int = 400,
    timeout: int = 90,
) -> str:
    """
    짧은 텍스트 요약(요약 텍스트만 반환)
    """
    r = clova_client.chat(
        system_text="너는 상담 요약 생성기다. 반드시 JSON만 출력한다. 키는 summary 하나만.",
        user_text=_prompt_summary_only(dialog_text, summary_max_len),
        temperature=0.0,
        timeout=timeout,
    )
    content = r["result"]["message"]["content"]

    # JSON 파싱 -> summary 추출 시도, 실패하면 원문 사용
    try:
        obj = _extract_json_object(content)
        summary = _safe_str(obj.get("summary", ""))
    except Exception:
        summary = _safe_str(content)

    summary = clean_summary_for_db(summary)
    summary = _truncate(summary if summary else "요약 내용 없음", summary_max_len)

    # 혹시 여전히 길면 한번 더 압축
    if len(summary) > summary_max_len:
        summary = compress_summary(clova_client, summary, summary_max_len=summary_max_len)

    return summary


def compress_summary(clova_client, summary_text: str, *, summary_max_len: int = 400, timeout: int = 60) -> str:
    """
    이미 만든 요약을 max_len 이내로 한번 더 압축
    """
    r = clova_client.chat(
        system_text="너는 요약 압축기다. 반드시 JSON만 출력한다. 키는 summary 하나만.",
        user_text=_prompt_compress(summary_text, summary_max_len),
        temperature=0.0,
        timeout=timeout,
    )
    content = r["result"]["message"]["content"]

    try:
        obj = _extract_json_object(content)
        summary = _safe_str(obj.get("summary", ""))
    except Exception:
        summary = _safe_str(content)

    summary = clean_summary_for_db(summary)
    summary = _truncate(summary if summary else "요약 내용 없음", summary_max_len)
    return summary


def summarize_long_dialog(
    clova_client,
    dialog_text: str,
    *,
    summary_max_len: int = 400,
) -> str:
    """
    긴 대화: 청크 요약 -> 최종 요약
    """
    chunks = chunk_text_by_chars(dialog_text, chunk_size=6000, overlap=400)
    if not chunks:
        return "요약 내용 없음"

    if len(chunks) == 1:
        return summarize_text(clova_client, chunks[0], summary_max_len=summary_max_len)

    # 1) 청크별 요약 (짧게)
    chunk_summaries: List[str] = []
    for i, ch in enumerate(chunks, 1):
        s = summarize_text(clova_client, ch, summary_max_len=900)
        chunk_summaries.append(f"[CHUNK {i}] {s}")

    # 2) 청크 요약들을 다시 최종 요약
    combined = "\n".join(chunk_summaries)
    final_summary = summarize_text(clova_client, combined, summary_max_len=summary_max_len)
    return final_summary


def classify_topic_only(
    clova_client,
    summary_text: str,
    topics: List[Dict[str, Any]],
    *,
    timeout: int = 60,
) -> int:
    """
    summary 기반으로 topic_id만 선택 (짧은 출력이라 잘림 거의 없음)
    """
    if not topics:
        raise ValueError("topics is empty")

    allowed = {int(t["id"]) for t in topics if "id" in t}
    default_id = int(topics[0]["id"])

    r = clova_client.chat(
        system_text="너는 토픽 분류기다. 반드시 JSON만 출력한다. 키는 topic_id 하나만.",
        user_text=_prompt_topic_only(summary_text, topics),
        temperature=0.0,
        timeout=timeout,
    )
    content = r["result"]["message"]["content"]

    try:
        obj = _extract_json_object(content)
        tid = int(obj.get("topic_id", default_id))
    except Exception:
        tid = default_id

    if tid not in allowed:
        tid = default_id
    return tid


def analyze_feature2(
    clova_client,
    dialog_text: str,
    *,
    topics: Optional[List[Dict[str, Any]]] = None,
    summary_max_len: int = 400,
) -> Dict[str, Any]:
    """
    최종 API:
    - summary는 항상 텍스트로 정리된 값
    - topics가 있으면 topic_id까지 추천
    반환:
      topics=None: {"summary": "..."}
      topics=... : {"summary": "...", "topic_id": N}
    """
    summary_text = summarize_long_dialog(clova_client, dialog_text, summary_max_len=summary_max_len)

    out: Dict[str, Any] = {"summary": summary_text}

    if topics is not None:
        out["topic_id"] = classify_topic_only(clova_client, summary_text, topics)

    return out


def make_sess_analysis_row(
    *,
    sess_id: int,
    topic_id: int,
    summary: str,
    counselor_note: str,
    summary_max_len: int = 4000,
    note_max_len: int = 2000,
) -> Dict[str, Any]:
    """
    sess_analysis 저장 row 생성
    - note는 상담사 입력 그대로 저장
    """
    s = _truncate(clean_summary_for_db(summary), summary_max_len)
    n = _truncate(_safe_str(counselor_note), note_max_len)

    if not _safe_str(s):
        s = "요약 내용 없음"
    if not _safe_str(n):
        n = "상담사 의견 미입력"

    return {"sess_id": int(sess_id), "topic_id": int(topic_id), "summary": s, "note": n}