
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List, Dict, Any
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from db import get_db
from schemas import SessionItem, QualityItem
import os
from dotenv import load_dotenv

load_dotenv()   # ⭐ 이 한 줄이 핵심

app = FastAPI(title="Mindway API", version="0.3.1")

# =========================================================
# 0) Request Models
# =========================================================
class SendMessage(BaseModel):
    sess_id: int = Field(..., ge=1)
    speaker: str = Field(..., pattern="^(COUNSELOR|CLIENT|SYSTEM)$")
    speaker_id: Optional[int] = Field(None, ge=1)
    text: Optional[str] = None
    emoji: Optional[str] = None
    file_url: Optional[str] = None
    stt_conf: float = 0.0

# =========================================================
# 1) Real-time Dropout Detection (Rule-based)
# =========================================================
NEGATIVE_KEYWORDS = [
    "그만", "힘들", "포기", "의미없", "못하겠",
    "지쳤", "짜증", "답답", "싫다", "괴롭"
]
SHORT_RESPONSES = ["네", "몰라요", "됐어요", "그냥요"]

def detect_dropout_signal(message: Optional[str]) -> Optional[Dict[str, Any]]:
    if not message:
        return None

    msg = message.strip()
    score = 0.0
    rules = []

    for kw in NEGATIVE_KEYWORDS:
        if kw in msg:
            score += 0.5
            rules.append("NEG_KEYWORD")
            break

    if msg in SHORT_RESPONSES:
        score += 0.4
        rules.append("SHORT_RESPONSE")

    if len(msg) <= 2:
        score += 0.2
        rules.append("VERY_SHORT")

    if score >= 0.5:
        return {
            "type": "RISK_WORD",   # ✅ DB 제약조건에 맞춤
            "status": "OPEN",
            "score": round(min(score, 1.0), 3),
            "rule": "|".join(rules) if rules else "RULE_ENGINE",
            "action": "WATCH"
        }

    return None

# =========================================================
# 2) Dashboard Risk Score (0~1)
# =========================================================
def calc_risk_score(alerts: List[Dict[str, Any]]) -> float:
    if not alerts:
        return 0.0

    weights = {
        "DROPOUT_RISK": 0.7,
        "NEG_SPIKE": 0.45,
        "DELAY": 0.25,
        "SHORT": 0.15,
        "RISK_WORD": 0.60,
    }

    total = 0.0
    for a in alerts:
        t = a.get("type")
        w = weights.get(t, 0.1)
        s = float(a["score"]) if a.get("score") is not None else 0.5
        total += w * s

    return round(min(total, 1.0), 3)

# =========================================================
# 3) Health
# =========================================================
@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    v = db.execute(text("SELECT 1")).scalar()
    return {"db": "ok", "ping": v}

# =========================================================
# 4) Sessions - 대시보드 호환 최적화 버전
# =========================================================

@app.get("/sessions", response_model=dict)
def list_sessions(
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    # 명시적으로 컬럼을 지정하여 데이터 누락 방지
    query = text("""
        SELECT id, uuid, counselor_id, client_id, channel, progress, created_at
        FROM sess
        ORDER BY id DESC
        LIMIT :limit
    """)
    
    result = db.execute(query, {"limit": limit}).mappings().all()
    
    # 결과를 딕셔너리 리스트로 변환하여 JSON 직렬화 안정성 확보
    rows = [dict(row) for row in result]
    
    # 스트림릿이 기대하는 'items'와 'count' 형식으로 반환
    return {
        "items": jsonable_encoder(rows), 
        "count": len(rows)
    }

@app.get("/sessions/{sess_id}")
def get_session(sess_id: int, db: Session = Depends(get_db)):
    # 특정 세션 상세 조회
    query = text("SELECT * FROM sess WHERE id = :sid")
    row = db.execute(query, {"sid": sess_id}).mappings().first()
    
    if not row:
        # 데이터가 없을 때 404 에러를 반환
        raise HTTPException(status_code=404, detail="Session not found")
        
    return dict(row)

# =========================================================
# 5) Messages (List)
# =========================================================
@app.get("/sessions/{sess_id}/messages", response_model=dict)
def list_messages(
    sess_id: int,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    rows = db.execute(text("""
        SELECT id, sess_id, speaker, speaker_id, text, emoji, file_url, stt_conf, at
        FROM msg
        WHERE sess_id = :sid
        ORDER BY id ASC
        LIMIT :limit
    """), {"sid": sess_id, "limit": limit}).mappings().all()

    return {"items": jsonable_encoder(rows), "count": len(rows)}

# =========================================================
# 6) Alerts (List)
# =========================================================
@app.get("/sessions/{sess_id}/alerts", response_model=dict)
def list_alerts(sess_id: int, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT id, sess_id, msg_id, type, status, score, rule, action, at
        FROM alert
        WHERE sess_id = :sid
        ORDER BY id DESC
    """), {"sid": sess_id}).mappings().all()

    return {"items": jsonable_encoder(rows), "count": len(rows)}

# =========================================================
# 7) Messages (Create) ✅ 실시간 탐지 + alert 자동 생성
# =========================================================
@app.post("/messages", response_model=dict)
def create_message(payload: SendMessage, db: Session = Depends(get_db)):

    exists = db.execute(text("SELECT 1 FROM sess WHERE id = :sid"), {"sid": payload.sess_id}).scalar()
    if not exists:
        raise HTTPException(status_code=404, detail="Session not found")

    speaker_id = payload.speaker_id
    if payload.speaker == "SYSTEM":
        speaker_id = None

    result = db.execute(text("""
        INSERT INTO msg (sess_id, speaker, speaker_id, text, emoji, file_url, stt_conf, at)
        VALUES (:sid, :speaker, :speaker_id, :text, :emoji, :file_url, :stt_conf, NOW())
    """), {
        "sid": payload.sess_id,
        "speaker": payload.speaker,
        "speaker_id": speaker_id,
        "text": payload.text,
        "emoji": payload.emoji,
        "file_url": payload.file_url,
        "stt_conf": payload.stt_conf,
    })
    msg_id = result.lastrowid

    detection = None
    if payload.speaker == "CLIENT":
        detection = detect_dropout_signal(payload.text)
        if detection:
            db.execute(text("""
                INSERT INTO alert (sess_id, msg_id, type, status, score, rule, action, at)
                VALUES (:sid, :mid, :type, :status, :score, :rule, :action, NOW())
            """), {
                "sid": payload.sess_id,
                "mid": msg_id,
                "type": detection["type"],
                "status": detection["status"],
                "score": detection["score"],
                "rule": detection["rule"],
                "action": detection["action"],
            })

    db.commit()
    return {"status": "saved", "msg_id": msg_id, "detection": detection}

# =========================================================
# 8) Quality
# =========================================================
@app.get("/sessions/{sess_id}/quality", response_model=Optional[QualityItem])
def get_quality(sess_id: int, db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT id, sess_id, flow, score, created_at
        FROM quality
        WHERE sess_id = :sid
    """), {"sid": sess_id}).mappings().first()
    return row

# =========================================================
# 9) Session Analysis
# =========================================================
@app.get("/sessions/{sess_id}/analysis", response_model=dict)
def list_session_analysis(sess_id: int, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT id, sess_id, topic_id, summary, note, created_at
        FROM sess_analysis
        WHERE sess_id = :sid
        ORDER BY id DESC
    """), {"sid": sess_id}).mappings().all()
    return {"items": jsonable_encoder(rows), "count": len(rows)}

# =========================================================
# 10) Dashboard
# =========================================================
@app.get("/sessions/{sess_id}/dashboard", response_model=dict)
def get_dashboard(sess_id: int, db: Session = Depends(get_db)):

    sess = db.execute(text("SELECT * FROM sess WHERE id = :sid"), {"sid": sess_id}).mappings().first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    msgs = db.execute(text("""
        SELECT id, sess_id, speaker, speaker_id, text, emoji, file_url, stt_conf, at
        FROM msg
        WHERE sess_id = :sid
        ORDER BY id ASC
        LIMIT 500
    """), {"sid": sess_id}).mappings().all()

    alerts = db.execute(text("""
        SELECT id, sess_id, msg_id, type, status, score, rule, action, at
        FROM alert
        WHERE sess_id = :sid
        ORDER BY id DESC
    """), {"sid": sess_id}).mappings().all()

    quality = db.execute(text("""
        SELECT id, sess_id, flow, score, created_at
        FROM quality
        WHERE sess_id = :sid
    """), {"sid": sess_id}).mappings().first()

    analysis = db.execute(text("""
        SELECT id, sess_id, topic_id, summary, note, created_at
        FROM sess_analysis
        WHERE sess_id = :sid
        ORDER BY id DESC
    """), {"sid": sess_id}).mappings().all()

    alerts_list = list(alerts) if alerts else []
    risk_score = calc_risk_score(alerts_list)

    return jsonable_encoder({
        "session": dict(sess),
        "messages": list(msgs) if msgs else [],
        "alerts": alerts_list,
        "quality": dict(quality) if quality else {},
        "analysis": list(analysis) if analysis else [],
        "risk_score": risk_score
    })