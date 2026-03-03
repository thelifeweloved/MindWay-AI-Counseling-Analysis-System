# services/session_repo.py
# DB에서 상담 대화 로더 - SQLAlchemy Session 사용으로 통일
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text


def load_dialog_text(db: Session, sess_id: int) -> str:
    """
    세션의 전체 대화를 "SPEAKER: 텍스트" 형태 문자열로 반환
    """
    result = db.execute(
        text("""
            SELECT sender_type, text
            FROM msg
            WHERE sess_id = :sess_id
            ORDER BY at ASC, id ASC
        """),
        {"sess_id": sess_id},
    ).fetchall()

    lines = []
    for row in result:
        text_val = (row.text or "").strip()
        if not text_val:
            continue
        # ✅ sender_type 대문자 정규화 → "CLIENT" 비교 정상 동작
        speaker = (row.sender_type or "UNKNOWN").strip().upper()
        lines.append(f"{speaker}: {text_val}")

    return "\n".join(lines)


def load_msg_rows(db: Session, sess_id: int) -> List[Dict[str, Any]]:
    """
    세션의 메시지를 feature1/3 분석용 dict 리스트로 반환
    """
    result = db.execute(
        text("""
            SELECT id, sender_type, text
            FROM msg
            WHERE sess_id = :sess_id
            ORDER BY at ASC, id ASC
        """),
        {"sess_id": sess_id},
    ).fetchall()

    out = []
    for i, row in enumerate(result):
        text_val = (row.text or "").strip()
        if not text_val:
            continue
        # ✅ sender_type 대문자 정규화
        speaker = (row.sender_type or "UNKNOWN").strip().upper()
        out.append({
            "idx": i,
            "msg_id": row.id,
            "speaker": speaker,
            "text": text_val,
        })
    return out
