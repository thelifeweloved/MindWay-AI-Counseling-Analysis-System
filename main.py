from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List, Dict, Any
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from db import get_db

load_dotenv()

app = FastAPI(title="Mindway Post-Analysis API", version="1.0.1")

# =========================================================
# Request Model
# =========================================================
class MessageCreate(BaseModel):
    sess_id: int = Field(..., ge=1)
    speaker: str = Field(..., pattern="^(COUNSELOR|CLIENT|SYSTEM)$")
    speaker_id: Optional[int] = Field(None, ge=1)
    text: Optional[str] = None
    emoji: Optional[str] = None
    file_url: Optional[str] = None
    stt_conf: float = Field(0.0, ge=0.0, le=1.0)

# =========================================================
# Logic
# =========================================================
def detect_dropout_signal(message: Optional[str]) -> Optional[Dict[str, Any]]:
    if not message:
        return None
    msg = message.strip()
    score = 0.0
    rules = []

    if any(kw in msg for kw in ["그만", "힘들", "포기", "싫어"]):
        score += 0.5
        rules.append("NEG_KEYWORD")

    if score >= 0.5:
        return {
            "type": "RISK_WORD",
            "status": "DETECTED",
            "score": round(min(score, 1.0), 2),
            "rule": "|".join(rules)[:50],
        }
    return None

# =========================================================
# Helpers
# =========================================================
def _rows(db: Session, sql: str, params: Dict[str, Any]):
    return db.execute(text(sql), params).mappings().all()

# =========================================================
# Health
# =========================================================
@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    v = db.execute(text("SELECT 1")).scalar()
    return {"db": "ok", "ping": v}

# =========================================================
# Sessions
# =========================================================
@app.get("/sessions")
def list_sessions(limit: int = Query(20, ge=1, le=200), db: Session = Depends(get_db)):
    sql = f"""
        SELECT * FROM sess
        ORDER BY id DESC
        LIMIT {int(limit)}
    """
    result = _rows(db, sql, {})
    return {"items": jsonable_encoder(result), "count": len(result)}

# =========================================================
# Messages
# =========================================================
@app.post("/messages")
def create_message(payload: MessageCreate, db: Session = Depends(get_db)):
    try:
        res = db.execute(text("""
            INSERT INTO msg (sess_id, speaker, speaker_id, text, emoji, file_url, stt_conf, at)
            VALUES (:sid, :speaker, :speaker_id, :text, :emoji, :file_url, :stt_conf, NOW())
        """), {
            "sid": payload.sess_id,
            "speaker": payload.speaker,
            "speaker_id": payload.speaker_id,
            "text": payload.text,
            "emoji": payload.emoji,
            "file_url": payload.file_url,
            "stt_conf": payload.stt_conf
        })

        msg_id = res.lastrowid
        detection = None

        if payload.speaker == "CLIENT":
            detection = detect_dropout_signal(payload.text)
            if detection:
                db.execute(text("""
                    INSERT INTO alert (sess_id, msg_id, type, status, score, rule, at)
                    VALUES (:sid, :mid, :type, :status, :score, :rule, NOW())
                """), {
                    "sid": payload.sess_id,
                    "mid": msg_id,
                    "type": detection["type"],
                    "status": detection["status"],
                    "score": detection["score"],
                    "rule": detection["rule"]
                })

        db.commit()
        return {"status": "saved", "msg_id": msg_id, "detection": detection}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# =========================================================
# Dashboard Support APIs
# =========================================================
@app.get("/stats/topic-dropout")
def topic_dropout(counselor_id: int, db: Session = Depends(get_db)):
    result = _rows(db, """
        SELECT channel, COUNT(*) as total,
        COUNT(CASE WHEN end_reason='DROPOUT' THEN 1 END)/COUNT(*)*100 as dropout_rate
        FROM sess
        WHERE counselor_id = :cid
        GROUP BY channel
    """, {"cid": counselor_id})
    return {"items": jsonable_encoder(result)}

@app.get("/stats/client-grade-dropout")
def client_grade_dropout(counselor_id: int, db: Session = Depends(get_db)):
    result = _rows(db, """
        SELECT c.status, COUNT(*) as total
        FROM client c
        JOIN sess s ON s.client_id = c.id
        WHERE s.counselor_id = :cid
        GROUP BY c.status
    """, {"cid": counselor_id})
    return {"items": jsonable_encoder(result)}
