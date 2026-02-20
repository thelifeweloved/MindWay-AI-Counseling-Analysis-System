import os
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List, Dict, Any
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

from db import get_db
# 하이퍼 클로바 X AI 상담 도우미 연결 (routers/helper.py)
from routers.helper import router as helper_router

# 1. 앱 초기화 및 미들웨어 설정 (순서 엄격 준수)
load_dotenv()
app = FastAPI(title="Mindway Post-Analysis API", version="1.0.2")

# [핵심] 브라우저(HTML) 연동을 위한 CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(helper_router)

# =========================================================
# 2. Pydantic Models (로그인 및 메시지 규격)
# =========================================================
class LoginRequest(BaseModel):
    email: str
    pwd: str

class MessageCreate(BaseModel):
    sess_id: int = Field(..., ge=1)
    speaker: str = Field(..., pattern="^(COUNSELOR|CLIENT|SYSTEM)$")
    speaker_id: Optional[int] = Field(None, ge=1)
    text: Optional[str] = None
    emoji: Optional[str] = None
    file_url: Optional[str] = None
    stt_conf: float = Field(0.0, ge=0.0, le=1.0)

# =========================================================
# 3. Helpers & Logic
# =========================================================
def _rows(db: Session, sql: str, params: Dict[str, Any]):
    return db.execute(text(sql), params).mappings().all()

def detect_dropout_signal(message: Optional[str]) -> Optional[Dict[str, Any]]:
    if not message:
        return None
    msg = message.strip()
    score = 0.0
    rules = []
    action = ""

    if any(kw in msg for kw in ["그만", "힘들", "포기", "싫어"]):
        score += 0.5
        rules.append("NEG_KEYWORD")
        action = "내담자의 부정적 감정이 감지되었습니다. 지지와 공감이 필요합니다."

    if score >= 0.5:
        return {
            "type": "RISK_WORD",
            "status": "DETECTED",
            "score": round(min(score, 1.0), 2),
            "rule": "|".join(rules)[:50],
            "action": action
        }
    return None

# =========================================================
# 4. Auth & Health Check
# =========================================================
@app.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """SMHRD DB의 counselor 테이블에서 계정을 확인합니다."""
    sql = "SELECT id, name FROM counselor WHERE email = :email AND pwd = :pwd"
    counselor = db.execute(text(sql), {"email": payload.email, "pwd": payload.pwd}).mappings().first()
    
    if not counselor:
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 일치하지 않습니다.")
    
    return {
        "status": "success",
        "counselor_id": counselor["id"],
        "counselor_name": counselor["name"]
    }

@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    """SMHRD 서버(3307)와의 연결 상태를 확인합니다."""
    try:
        v = db.execute(text("SELECT 1")).scalar()
        return {"db": "ok", "ping": v}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB Connection Error: {str(e)}")

# =========================================================
# 5. Core APIs (Sessions & Messages)
# =========================================================
@app.get("/sessions")
def list_sessions(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    sql = "SELECT * FROM sess ORDER BY id DESC LIMIT :l"
    result = db.execute(text(sql), {"l": limit}).mappings().all()
    return {"items": jsonable_encoder(result), "count": len(result)}

@app.post("/messages")
def create_message(payload: MessageCreate, db: Session = Depends(get_db)):
    try:
        sess_exists = db.execute(text("SELECT 1 FROM sess WHERE id = :sid"), {"sid": payload.sess_id}).scalar()
        if not sess_exists:
            raise HTTPException(status_code=404, detail="sess_id not found")

        res = db.execute(text("""
            INSERT INTO msg (sess_id, speaker, speaker_id, text, emoji, file_url, stt_conf, at)
            VALUES (:sid, :speaker, :speaker_id, :text, :emoji, :file_url, :stt_conf, NOW())
        """), {
            "sid": payload.sess_id, "speaker": payload.speaker, "speaker_id": payload.speaker_id,
            "text": payload.text, "emoji": payload.emoji, "file_url": payload.file_url, "stt_conf": payload.stt_conf
        })

        msg_id = res.lastrowid
        detection = None

        if payload.speaker == "CLIENT":
            detection = detect_dropout_signal(payload.text)
            if detection:
                db.execute(text("""
                    INSERT INTO alert (sess_id, msg_id, type, status, score, rule, action, at)
                    VALUES (:sid, :mid, :type, :status, :score, :rule, :action, NOW())
                """), {
                    "sid": payload.sess_id, "mid": msg_id, "type": detection["type"],
                    "status": detection["status"], "score": detection["score"],
                    "rule": detection["rule"], "action": detection["action"]
                })

        db.commit()
        return {"status": "saved", "msg_id": msg_id, "detection": detection}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/sessions/{sess_id}/dashboard")
def session_dashboard(sess_id: int, db: Session = Depends(get_db)):
    sess = db.execute(text("SELECT * FROM sess WHERE id = :sid"), {"sid": sess_id}).mappings().first()
    if not sess: raise HTTPException(status_code=404, detail="sess_id not found")
    risk_score = db.execute(text("SELECT COALESCE(AVG(score), 0) FROM alert WHERE sess_id = :sid"), {"sid": sess_id}).scalar()
    return {"session": jsonable_encoder(sess), "risk_score": float(risk_score or 0.0)}

@app.get("/sessions/{sess_id}/messages")
def session_messages(sess_id: int, limit: int = Query(200, ge=1), db: Session = Depends(get_db)):
    sql = "SELECT id, sess_id, speaker, speaker_id, text, emoji, file_url, stt_conf, at FROM msg WHERE sess_id = :sid ORDER BY at DESC LIMIT :l"
    result = db.execute(text(sql), {"sid": sess_id, "l": limit}).mappings().all()
    return {"items": jsonable_encoder(list(result))}

@app.get("/sessions/{sess_id}/alerts")
def session_alerts(sess_id: int, db: Session = Depends(get_db)):
    result = db.execute(text("SELECT * FROM alert WHERE sess_id = :sid ORDER BY at DESC LIMIT 200"), {"sid": sess_id}).mappings().all()
    return {"items": jsonable_encoder(list(result))}

@app.get("/appointments")
def get_appointments(counselor_id: int = Query(..., ge=1), db: Session = Depends(get_db)):
    sql = "SELECT a.id, c.name AS client_name, a.at, a.status, c.status AS client_grade FROM appt a JOIN client c ON a.client_id = c.id WHERE a.counselor_id = :cid ORDER BY a.at ASC"
    result = db.execute(text(sql), {"cid": counselor_id}).mappings().all()
    return {"items": jsonable_encoder(list(result))}

# =========================================================
# 6. Stats APIs (통계 로직 보존)
# =========================================================
@app.get("/stats/topic-dropout")
def topic_dropout(counselor_id: int = Query(..., ge=1), db: Session = Depends(get_db)):
    """
    주제별 이탈 분석 (가이드라인 제공 목적)
    """
    # 명세서 기반으로 sess_analysis와 topic 테이블 조인 유지
    sql = """
        SELECT 
            t.name AS topic_name, 
            COUNT(s.id) AS total,
            (COUNT(CASE WHEN s.end_reason='DROPOUT' THEN 1 END) / NULLIF(COUNT(s.id), 0)) * 100 AS dropout_rate,
            AVG(s.sat) * 100 AS avg_sat_rate
        FROM topic t 
        JOIN sess_analysis sa ON t.id = sa.topic_id 
        JOIN sess s ON sa.sess_id = s.id
        WHERE s.counselor_id = :cid 
        GROUP BY t.id 
        ORDER BY dropout_rate DESC
    """
    result = db.execute(text(sql), {"cid": counselor_id}).mappings().all()
    return {"items": jsonable_encoder(list(result))}

@app.get("/stats/quality-trend")
def quality_trend(counselor_id: int = Query(..., ge=1), db: Session = Depends(get_db)):
    """
    서브쿼리 없이 JOIN과 GROUP BY만 사용하여 모든 MySQL 환경에서 동작하도록 수정
    """
    # 1. 날짜별 만족도 평균과 리스크 점수 평균을 한 번에 계산하는 정석 쿼리
    sql = """
        SELECT 
            DATE(s.start_at) AS date_label,
            AVG(s.sat) * 100 AS avg_sat_rate,
            AVG(a.score) AS avg_risk_score
        FROM sess s
        LEFT JOIN alert a ON s.id = a.sess_id
        WHERE s.counselor_id = :cid
        GROUP BY DATE(s.start_at)
        ORDER BY DATE(s.start_at) ASC
    """
    try:
        result = db.execute(text(sql), {"cid": counselor_id}).mappings().all()
        
        formatted_result = []
        for row in result:
            # MySQL 날짜 객체를 프론트엔드용 문자열(MM-DD)로 변환
            d_label = row["date_label"]
            date_str = d_label.strftime('%m-%d') if d_label else "00-00"
            
            formatted_result.append({
                "date_label": date_str,
                "avg_sat_rate": float(row["avg_sat_rate"] or 0),
                "avg_risk_score": float(row["avg_risk_score"] or 0)
            })
        
        return {"items": jsonable_encoder(formatted_result)}
    except Exception as e:
        print(f"Query Error Detail: {str(e)}")
        raise HTTPException(status_code=500, detail="대시보드 통계 분석 오류")
    
@app.get("/stats/client-grade-dropout")
def client_grade_dropout(counselor_id: int = Query(..., ge=1), db: Session = Depends(get_db)):
    sql = "SELECT c.status AS client_grade, COUNT(*) AS total FROM client c JOIN sess s ON s.client_id = c.id WHERE s.counselor_id = :cid GROUP BY c.status ORDER BY total DESC"
    return {"items": jsonable_encoder(list(db.execute(text(sql), {"cid": counselor_id}).mappings().all()))}

@app.get("/stats/missed-alerts")
def stats_missed_alerts(counselor_id: int = Query(..., ge=1), db: Session = Depends(get_db)):
    sql = "SELECT s.id AS sess_id, s.uuid, s.start_at, s.end_at, TIMESTAMPDIFF(MINUTE, s.start_at, s.end_at) AS duration_min FROM sess s WHERE s.counselor_id = :cid AND s.end_reason = 'DROPOUT' AND (SELECT COUNT(*) FROM alert a WHERE a.sess_id = s.id) = 0 ORDER BY s.start_at DESC LIMIT 200"
    result = db.execute(text(sql), {"cid": counselor_id}).mappings().all()
    return {"items": jsonable_encoder(list(result))}

@app.get("/stats/time-dropout")
def stats_time_dropout(counselor_id: int = Query(..., ge=1), db: Session = Depends(get_db)):
    sql = "SELECT HOUR(s.start_at) AS hour, COUNT(*) AS total, (COUNT(CASE WHEN s.end_reason='DROPOUT' THEN 1 END) / NULLIF(COUNT(*),0)) * 100 AS dropout_rate FROM sess s WHERE s.counselor_id = :cid GROUP BY hour ORDER BY hour ASC"
    result = db.execute(text(sql), {"cid": counselor_id}).mappings().all()
    return {"items": jsonable_encoder(list(result))}

@app.get("/stats/channel-dropout")
def stats_channel_dropout(counselor_id: int = Query(..., ge=1), db: Session = Depends(get_db)):
    """
    채널별(CHAT/VOICE) 이탈률 및 평균 만족도 분석
    """
    sql = """
        SELECT 
            s.channel AS channel, 
            COUNT(*) AS total, 
            (COUNT(CASE WHEN s.end_reason='DROPOUT' THEN 1 END) / NULLIF(COUNT(*),0)) * 100 AS dropout_rate,
            AVG(s.sat) * 100 AS avg_sat_rate
        FROM sess s 
        WHERE s.counselor_id = :cid 
        GROUP BY s.channel 
        ORDER BY dropout_rate DESC
    """
    result = db.execute(text(sql), {"cid": counselor_id}).mappings().all()
    return {"items": jsonable_encoder(list(result))}
@app.get("/stats/monthly-growth")
def stats_monthly_growth(counselor_id: int = Query(..., ge=1), db: Session = Depends(get_db)):
    sql = "SELECT DATE_FORMAT(s.start_at, '%Y-%m') AS month, COUNT(*) AS total, (COUNT(CASE WHEN s.end_reason='DROPOUT' THEN 1 END) / NULLIF(COUNT(*),0)) * 100 AS dropout_rate FROM sess s WHERE s.counselor_id = :cid GROUP BY month ORDER BY month ASC"
    result = db.execute(text(sql), {"cid": counselor_id}).mappings().all()
    return {"items": jsonable_encoder(list(result))}