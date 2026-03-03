import os
import json
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List, Dict, Any
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid
import hashlib
from db import get_db
from routers.helper import router as helper_router
from routers.api import api_router
from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks #
from sqlalchemy.orm import Session

# from routers.analysis_services.runner import run_core_features
# from routers.analysis_services.clova_client import ClovaXClient

load_dotenv()
app = FastAPI(title="Mindway Post-Analysis API", version="1.1.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(helper_router)
app.include_router(api_router)
# ---------------------------------------------------------
# Pydantic Models (명세서 및 프론트엔드 연동 규격 반영)
# ---------------------------------------------------------
class LoginRequest(BaseModel):
    email: str
    pwd: str

class ClientLoginRequest(BaseModel):
    # 프론트엔드 Login.html 연동을 위해 email, pwd 방식으로 통일
    email: str
    pwd: str

class SignupRequest(BaseModel):
    role: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    pwd: Optional[str] = None

class MessageCreate(BaseModel):
    sess_id: int = Field(..., ge=1)
    speaker: str = Field(..., pattern="^(COUNSELOR|CLIENT|SYSTEM)$")
    speaker_id: Optional[int] = Field(None, ge=1)
    text: Optional[str] = None
    emoji: Optional[str] = None
    file_url: Optional[str] = None
    stt_conf: float = Field(0.0, ge=0.0, le=1.0)

class FaceSaveRequest(BaseModel):
    sess_id: int
    label:   str
    score:   float
    dist:    dict

class ConsentRequest(BaseModel):
    ok_text:  Optional[bool] = None
    ok_voice: Optional[bool] = None
    ok_face:  Optional[bool] = None

class QualityCreate(BaseModel):
    flow:  float = Field(..., ge=0.0, le=100.0)
    score: float = Field(..., ge=0.0, le=100.0)

class SttCreate(BaseModel):
    sess_id: int   = Field(..., ge=1)
    speaker: str   = Field(..., pattern="^(COUNSELOR|CLIENT)$")
    s_ms:    int   = Field(..., ge=0)
    e_ms:    int   = Field(..., ge=0)
    text:    str
    conf:    float = Field(0.0, ge=0.0, le=1.0)

class SessionCloseRequest(BaseModel):
    end_reason: str  = Field("NORMAL", pattern="^(NORMAL|DROPOUT|TECH|UNKNOWN)$")
    sat:         Optional[int] = Field(None, ge=0, le=1)
    sat_note:   Optional[str] = None

class AlertStatusUpdate(BaseModel):
    status: str

class NoteUpdateRequest(BaseModel):
    topic_id: Optional[int] = Field(1, ge=1)
    note: str

# [추가됨] Appt.html 예약 상태 및 배정 상담사 변경용 모델
class ApptUpdateRequest(BaseModel):
    counselor_id: Optional[int] = None
    status: Optional[str] = None

class ApptCreateRequest(BaseModel):
    client_id: int
    counselor_id: Optional[int] = None
    at: str

# ---------------------------------------------------------
# Helpers & Logic
# ---------------------------------------------------------
def hash_pwd(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()

def detect_dropout_signal(message: Optional[str]) -> Optional[Dict[str, Any]]:
    if not message:
        return None
    msg = message.strip()
    score = 0.0
    rules = []
    action = ""

    if any(kw in msg for kw in ["그만", "힘들", "포기", "싫어", "의미없"]):
        score += 0.5
        rules.append("NEG_KEYWORD")
        action = "내담자의 정서적 소진 신호가 감지되었습니다. 지지와 공감이 필요합니다."

    if score >= 0.5:
        return {
            "type": "CONTINUITY_SIGNAL",
            "status": "DETECTED",
            "score": round(min(score, 1.0), 2),
            "rule": "|".join(rules)[:50],
            "action": action
        }
    return None

# ---------------------------------------------------------
# Auth (테이블 명세서 기반 필수 필드 검증 적용)
# ---------------------------------------------------------

@app.post("/auth/signup")
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    try:
        role = (payload.role or "").strip().lower()

        if role == "counselor":
            if not payload.email:
                raise HTTPException(status_code=400, detail="상담사는 이메일이 필수입니다.")
            if not payload.pwd:
                raise HTTPException(status_code=400, detail="상담사는 비밀번호가 필수입니다.")
            sql = "INSERT INTO counselor (email, pwd, name) VALUES (:email, :pwd, :name)"
            params = {"email": payload.email, "pwd": hash_pwd(payload.pwd), "name": payload.name}
            db.execute(text(sql), params)

        elif role == "client":
            if not payload.email or not payload.pwd:
                raise HTTPException(status_code=400, detail="내담자 이메일과 비밀번호는 필수입니다.")

            clean_phone = "".join(filter(str.isdigit, payload.phone or ""))
            if not clean_phone:
                raise HTTPException(status_code=400, detail="연락처는 필수입니다.")
            
            sql = """
                INSERT INTO client (code, name, phone, email, pwd, status, active)
                VALUES (:code, :name, :phone, :email, :pwd, '안정', TRUE)
            """
            params = {
                "code": f"CL-{uuid.uuid4().hex[:8].upper()}",
                "name": payload.name,
                "phone": clean_phone,
                "email": payload.email,
                "pwd": hash_pwd(payload.pwd)
            }
            db.execute(text(sql), params)

        else:
            raise HTTPException(status_code=400, detail="role은 counselor 또는 client 여야 합니다.")

        db.commit()
        return {"status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"DEBUG DB ERROR: {str(e)}")
        raise HTTPException(status_code=400, detail=f"가입 처리 중 오류 발생: {str(e)}")


@app.post("/login")
def counselor_login(payload: LoginRequest, db: Session = Depends(get_db)):
    sql = "SELECT id, name FROM counselor WHERE email = :email AND pwd = :pwd"
    counselor = db.execute(text(sql), {"email": payload.email, "pwd": hash_pwd(payload.pwd)}).mappings().first()
    if counselor:
        return {"status": "success", "role": "counselor", "counselor_id": counselor["id"], "counselor_name": counselor["name"]}
    raise HTTPException(status_code=401, detail="계정 정보가 일치하지 않습니다.")


@app.post("/client/login")
def client_login(payload: ClientLoginRequest, db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT id, name, code FROM client
        WHERE email = :email AND pwd = :pwd AND active = TRUE LIMIT 1
    """), {"email": payload.email, "pwd": hash_pwd(payload.pwd)}).mappings().first()
    
    if not row:
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 일치하지 않습니다.")
    return {"status": "success", "role": "client", "client_id": row["id"], "client_name": row["name"], "client_code": row["code"]}


class ClientStartSessionRequest(BaseModel):
    client_id: int = Field(..., ge=1)
    counselor_id: int = Field(..., ge=1)

@app.post("/client/start-session")
def client_start_session(payload: ClientStartSessionRequest, db: Session = Depends(get_db)):
    existing = db.execute(text("""
        SELECT id FROM sess
        WHERE client_id = :clid AND counselor_id = :coid
          AND (end_at IS NULL) AND (progress IN ('WAITING','ACTIVE'))
        ORDER BY id DESC LIMIT 1
    """), {"clid": payload.client_id, "coid": payload.counselor_id}).scalar()
    if existing:
        return {"status": "success", "sess_id": int(existing), "reused": True}
    new_uuid = str(uuid.uuid4())
    res = db.execute(text("""
        INSERT INTO sess (uuid, counselor_id, client_id, channel, progress)
        VALUES (:uuid, :coid, :clid, 'CHAT', 'ACTIVE')
    """), {"uuid": new_uuid, "coid": payload.counselor_id, "clid": payload.client_id})
    db.commit()
    return {"status": "success", "sess_id": int(res.lastrowid), "reused": False}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    try:
        v = db.execute(text("SELECT 1")).scalar()
        return {"db": "ok", "ping": v, "port": 3307}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB Connection Error: {str(e)}")

# ---------------------------------------------------------
# Core APIs
# ---------------------------------------------------------
@app.get("/sessions")
def list_sessions(counselor_id: Optional[int] = Query(None, ge=1), limit: int = Query(50), db: Session = Depends(get_db)):
    sql = """
        SELECT s.*, c.name AS client_name, c.status AS client_status
        FROM sess s JOIN client c ON c.id = s.client_id
        WHERE (:cid IS NULL OR s.counselor_id = :cid)
        ORDER BY s.id DESC LIMIT :l
    """
    result = db.execute(text(sql), {"cid": counselor_id, "l": limit}).mappings().all()
    return {"items": jsonable_encoder(result)}

@app.post("/messages")
def create_message(payload: MessageCreate, db: Session = Depends(get_db)):
    try:
        res = db.execute(text("""
            INSERT INTO msg (sess_id, sender_type, sender_id, text, file_url, at)
            VALUES (:sid, :speaker, :speaker_id, :text, :file_url, NOW())
        """), {
            "sid": payload.sess_id, "speaker": payload.speaker,
            "speaker_id": None if payload.speaker == "SYSTEM" else payload.speaker_id,
            "text": payload.text, "file_url": payload.file_url
        })
        msg_id = res.lastrowid
        db.commit() 

        detection = None
        # [수정됨] 이미지 데이터(Base64)인 경우 감정 분석 및 이탈 신호 감지를 건너뜀
        if payload.speaker == "CLIENT" and payload.text and not payload.text.startswith("data:image"):
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
                
            _t = payload.text
            _high  = ["죽고싶", "자해", "사라지고싶", "없어지고싶", "끝내고싶"]
            _neg   = ["그만", "포기", "싫어", "힘들", "못하겠", "의미없", "안 할래"]
            _pos   = ["감사", "좋아", "행복", "기쁘", "즐거", "다행"]
            
            if any(k in _t for k in _high): _label, _score = "fear", 0.90
            elif any(k in _t for k in _neg): _label, _score = "sad", 0.70
            elif any(k in _t for k in _pos): _label, _score = "happy", 0.70
            else: _label, _score = "neutral", 0.50
                
            db.execute(text("""
                INSERT INTO text_emotion (msg_id, label, score, meta)
                VALUES (:mid, :label, :score, :meta)
            """), {
                "mid": msg_id, "label": _label, "score": _score,
                "meta": json.dumps({"engine": "rule", "version": "1.0"})
            })

        db.commit()
        return {"status": "saved", "msg_id": msg_id, "detection": detection}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/sessions/{sess_id}/dashboard")
def session_dashboard(sess_id: int, db: Session = Depends(get_db)):
    sess = db.execute(text("""
        SELECT s.*, c.name AS client_name, c.status AS client_status
        FROM sess s JOIN client c ON c.id = s.client_id WHERE s.id = :sid
    """), {"sid": sess_id}).mappings().first()
    if not sess: raise HTTPException(status_code=404, detail="sess_id not found")
    
    risk_score = float(db.execute(text("SELECT COALESCE(AVG(score), 0) FROM alert WHERE sess_id = :sid"), {"sid": sess_id}).scalar() or 0.0)
    topic_analysis = db.execute(text("""
        SELECT sa.topic_id, t.name as topic_name, sa.summary, sa.note
        FROM sess_analysis sa LEFT JOIN topic t ON sa.topic_id = t.id WHERE sa.sess_id = :sid
    """), {"sid": sess_id}).mappings().all()

    total_alerts = int(db.execute(text("SELECT COUNT(*) FROM alert WHERE sess_id = :sid"), {"sid": sess_id}).scalar() or 0)
    alert_types_rows = db.execute(text("""
        SELECT type, COUNT(*) AS cnt
        FROM alert WHERE sess_id = :sid
        GROUP BY type ORDER BY cnt DESC
    """), {"sid": sess_id}).mappings().all()
    alert_types = [{"type": r["type"], "cnt": int(r["cnt"])} for r in alert_types_rows]

    # [수정됨] SessionDetail.html 리포트 출력을 위한 quality 데이터 매핑
    quality = {"flow": 0.0, "score": 0.0, "churn_prob": risk_score}
    try:
        quality_row = db.execute(text("SELECT flow, score FROM quality WHERE sess_id = :sid LIMIT 1"), {"sid": sess_id}).mappings().first()
        if quality_row:
            quality["flow"] = float(quality_row["flow"] or 0)
            quality["score"] = float(quality_row["score"] or 0)
    except: pass

    return {
        "session": jsonable_encoder(sess),
        "risk_score": risk_score,
        "topic_analysis": jsonable_encoder(topic_analysis),
        "risk_label": "HIGH" if risk_score >= 0.7 else "MID" if risk_score >= 0.4 else "LOW",
        "alert_summary": {"total_alerts": total_alerts},
        "alert_types": alert_types,
        "quality": quality
    }

@app.get("/sessions/{sess_id}/messages")
def session_messages(sess_id: int, limit: int = Query(200, ge=1), db: Session = Depends(get_db)):
    result = db.execute(text("""
        SELECT id, sess_id, sender_type AS speaker, sender_id AS speaker_id, text, file_url, at
        FROM msg
        WHERE sess_id = :sid ORDER BY at ASC LIMIT :l
    """), {"sid": sess_id, "l": limit}).mappings().all()
    return {"items": jsonable_encoder(list(result))}

@app.get("/sessions/{sess_id}/alerts")
def session_alerts(sess_id: int, limit: int = Query(200, ge=1), db: Session = Depends(get_db)):
    result = db.execute(text("SELECT * FROM alert WHERE sess_id = :sid ORDER BY at DESC LIMIT :l"), {"sid": sess_id, "l": limit}).mappings().all()
    return {"items": jsonable_encoder(list(result))}

@app.get("/sessions/{sess_id}/emotions")
def session_emotions(sess_id: int, db: Session = Depends(get_db)):
    result = db.execute(text("""
        SELECT te.id, te.msg_id, te.label, te.score, te.meta, m.at AS created_at
        FROM text_emotion te
        JOIN msg m ON te.msg_id = m.id
        WHERE m.sess_id = :sid
        ORDER BY m.at ASC
    """), {"sid": sess_id}).mappings().all()
    return {"items": jsonable_encoder(list(result))}

@app.get("/appointments")
def get_appointments(counselor_id: Optional[int] = Query(None), client_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    sql = """
        SELECT a.id, a.client_id, a.counselor_id, c.name AS client_name, a.at, a.status, a.created_at
        FROM appt a 
        JOIN client c ON a.client_id = c.id 
        WHERE (:cid IS NULL OR a.counselor_id = :cid) 
          AND (:clid IS NULL OR a.client_id = :clid)
        ORDER BY a.at ASC
    """
    result = db.execute(text(sql), {"cid": counselor_id, "clid": client_id}).mappings().all()
    return {"items": jsonable_encoder(list(result))}

@app.get("/counselors")
def get_counselors(db: Session = Depends(get_db)):
    sql = "SELECT id, name FROM counselor"
    result = db.execute(text(sql)).mappings().all()
    return {"items": jsonable_encoder(list(result))}

# [추가됨] Appt.html 예약 상태 및 배정 상담사 변경 로직
@app.patch("/appointments/{appt_id}")
def update_appointment(appt_id: int, payload: ApptUpdateRequest, db: Session = Depends(get_db)):
    try:
        fields = {}
        if payload.counselor_id is not None:
            fields["counselor_id"] = payload.counselor_id
        if payload.status is not None:
            fields["status"] = payload.status
            
        if not fields:
            raise HTTPException(status_code=400, detail="업데이트할 항목이 없습니다.")
            
        set_clause = ", ".join([f"{k} = :{k}" for k in fields])
        fields["appt_id"] = appt_id
        
        db.execute(text(f"UPDATE appt SET {set_clause} WHERE id = :appt_id"), fields)
        db.commit()
        return {"status": "updated"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# ---------------------------------------------------------
# Stats APIs
# ---------------------------------------------------------
@app.get("/stats/topic-dropout")
def topic_dropout(counselor_id: int = Query(..., ge=1), db: Session = Depends(get_db)):
    sql = """
        SELECT t.name AS topic_name, COUNT(s.id) AS total,
               (COUNT(CASE WHEN s.end_reason='DROPOUT' THEN 1 END) / NULLIF(COUNT(s.id), 0)) * 100 AS dropout_rate,
               AVG(s.sat) * 100 AS avg_sat_rate
        FROM topic t JOIN sess_analysis sa ON t.id = sa.topic_id JOIN sess s ON sa.sess_id = s.id
        WHERE s.counselor_id = :cid GROUP BY t.id ORDER BY dropout_rate DESC
    """
    return {"items": jsonable_encoder(list(db.execute(text(sql), {"cid": counselor_id}).mappings().all()))}

@app.get("/stats/quality-trend")
def quality_trend(counselor_id: int = Query(..., ge=1), db: Session = Depends(get_db)):
    sql = """
        SELECT DATE(s.start_at) AS date_label,
               AVG(s.sat) * 100         AS avg_sat_rate,
               AVG(a.score)             AS avg_risk_score,
               AVG(q.flow)              AS avg_flow,
               AVG(q.score)             AS avg_quality_score
        FROM sess s
        LEFT JOIN alert   a ON s.id = a.sess_id
        LEFT JOIN quality q ON s.id = q.sess_id
        WHERE s.counselor_id = :cid
        GROUP BY DATE(s.start_at)
        ORDER BY DATE(s.start_at) ASC
    """
    result = db.execute(text(sql), {"cid": counselor_id}).mappings().all()
    formatted = [{
        "date_label":        r["date_label"].strftime('%m-%d') if hasattr(r["date_label"], "strftime") else str(r["date_label"]),
        "avg_sat_rate":      float(r["avg_sat_rate"]      or 0),
        "avg_risk_score":    float(r["avg_risk_score"]    or 0),
        "avg_flow":          float(r["avg_flow"]          or 0),
        "avg_quality_score": float(r["avg_quality_score"] or 0)
    } for r in result]
    return {"items": jsonable_encoder(formatted)}

@app.get("/stats/client-grade-dropout")
def client_grade_dropout(counselor_id: int = Query(..., ge=1), db: Session = Depends(get_db)):
    sql = "SELECT c.status AS client_grade, COUNT(*) AS total FROM client c JOIN sess s ON s.client_id = c.id WHERE s.counselor_id = :cid GROUP BY c.status ORDER BY total DESC"
    return {"items": jsonable_encoder(list(db.execute(text(sql), {"cid": counselor_id}).mappings().all()))}

@app.get("/stats/time-dropout")
def stats_time_dropout(counselor_id: int = Query(..., ge=1), db: Session = Depends(get_db)):
    sql = "SELECT HOUR(s.start_at) AS hour, COUNT(*) AS total, (COUNT(CASE WHEN s.end_reason='DROPOUT' THEN 1 END) / NULLIF(COUNT(*),0)) * 100 AS dropout_rate FROM sess s WHERE s.counselor_id = :cid GROUP BY hour ORDER BY hour ASC"
    return {"items": jsonable_encoder(list(db.execute(text(sql), {"cid": counselor_id}).mappings().all()))}

@app.get("/stats/channel-dropout")
def stats_channel_dropout(counselor_id: int = Query(..., ge=1), db: Session = Depends(get_db)):
    sql = "SELECT s.channel, COUNT(*) AS total, (COUNT(CASE WHEN s.end_reason='DROPOUT' THEN 1 END) / NULLIF(COUNT(*),0)) * 100 AS dropout_rate, AVG(s.sat) * 100 AS avg_sat_rate FROM sess s WHERE s.counselor_id = :cid GROUP BY s.channel ORDER BY dropout_rate DESC"
    return {"items": jsonable_encoder(list(db.execute(text(sql), {"cid": counselor_id}).mappings().all()))}

@app.get("/stats/monthly-growth")
def stats_monthly_growth(counselor_id: int = Query(..., ge=1), db: Session = Depends(get_db)):
    sql = "SELECT DATE_FORMAT(s.start_at, '%Y-%m') AS month, COUNT(*) AS total, (COUNT(CASE WHEN s.end_reason='DROPOUT' THEN 1 END) / NULLIF(COUNT(*),0)) * 100 AS dropout_rate FROM sess s WHERE s.counselor_id = :cid GROUP BY month ORDER BY month ASC"
    return {"items": jsonable_encoder(list(db.execute(text(sql), {"cid": counselor_id}).mappings().all()))}

# ---------------------------------------------------------
# 얼굴 감정 분석 저장 및 동의, STT, Quality 연동 API
# ---------------------------------------------------------

@app.post("/face/save")
def save_face(payload: FaceSaveRequest, db: Session = Depends(get_db)):
    try:
        ok = db.execute(text("SELECT ok_face FROM sess WHERE id = :sid"), {"sid": payload.sess_id}).scalar()
        if not ok: return {"status": "skipped", "reason": "ok_face 미동의"}

        db.execute(text("""
            INSERT INTO face (sess_id, at, label, score, dist, meta)
            VALUES (:sess_id, NOW(), :label, :score, :dist, :meta)
        """), {
            "sess_id": payload.sess_id, "label": payload.label, "score": payload.score,
            "dist": json.dumps(payload.dist), "meta": json.dumps({"engine": "deepface", "version": "0.4"})
        })
        db.commit()
        return {"status": "saved"}
    except Exception as e:
        db.rollback(); raise HTTPException(status_code=400, detail=str(e))

@app.patch("/sessions/{sess_id}/consent")
def update_consent(sess_id: int, payload: ConsentRequest, db: Session = Depends(get_db)):
    try:
        fields = {k: v for k, v in payload.dict().items() if v is not None}
        if not fields: raise HTTPException(status_code=400, detail="업데이트할 항목이 없습니다.")
        set_clause = ", ".join([f"{k} = :{k}" for k in fields])
        fields["sess_id"] = sess_id
        db.execute(text(f"UPDATE sess SET {set_clause} WHERE id = :sess_id"), fields)
        db.commit()
        return {"status": "updated"}
    except Exception as e:
        db.rollback(); raise HTTPException(status_code=400, detail=str(e))

@app.get("/sessions/{sess_id}/consent")
def get_consent(sess_id: int, db: Session = Depends(get_db)):
    row = db.execute(text("SELECT ok_text, ok_voice, ok_face FROM sess WHERE id = :sid"), {"sid": sess_id}).mappings().first()
    if not row: raise HTTPException(status_code=404, detail="세션 없음")
    return {"ok_text": bool(row["ok_text"]), "ok_voice": bool(row["ok_voice"]), "ok_face": bool(row["ok_face"])}

@app.get("/stats/recent-alerts")
def recent_alerts(counselor_id: int = Query(..., ge=1), db: Session = Depends(get_db)):
    sql = """
        SELECT a.id, a.sess_id, a.msg_id, a.type, a.status, a.score, a.rule, a.at, a.action AS reasonMsg,
               c.name AS client_name
        FROM alert a JOIN sess s ON a.sess_id = s.id JOIN client c ON s.client_id = c.id
        WHERE s.counselor_id = :cid AND a.status = 'DETECTED'
        ORDER BY a.score DESC LIMIT 20
    """
    result = db.execute(text(sql), {"cid": counselor_id}).mappings().all()
    return {"items": jsonable_encoder(list(result))}

# UC-07: 상담사 의견 메모 저장 (sess_analysis.note 업데이트)
@app.patch("/sessions/{sess_id}/analysis")
def update_analysis_note(sess_id: int, payload: NoteUpdateRequest, db: Session = Depends(get_db)):
    try:
        tid = payload.topic_id or 1
        row = db.execute(text("""
            SELECT id FROM sess_analysis WHERE sess_id = :sid AND topic_id = :tid
        """), {"sid": sess_id, "tid": tid}).scalar()

        if not row:
            db.execute(text("""
                INSERT INTO sess_analysis (sess_id, topic_id, summary, note)
                VALUES (:sid, :tid, '', :note)
            """), {"note": payload.note, "sid": sess_id, "tid": tid})
        else:
            db.execute(text("""
                UPDATE sess_analysis SET note = :note WHERE sess_id = :sid AND topic_id = :tid
            """), {"note": payload.note, "sid": sess_id, "tid": tid})
            
        db.commit()
        return {"status": "saved"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/sessions/{sess_id}/quality")
def save_quality(sess_id: int, payload: QualityCreate, db: Session = Depends(get_db)):
    try:
        db.execute(text("""
            INSERT INTO quality (sess_id, flow, score) VALUES (:sid, :flow, :score)
            ON DUPLICATE KEY UPDATE flow = :flow, score = :score
        """), {"sid": sess_id, "flow": payload.flow, "score": payload.score})
        db.commit()
        return {"status": "saved"}
    except Exception as e:
        db.rollback(); raise HTTPException(status_code=400, detail=str(e))

@app.post("/stt")
def create_stt(payload: SttCreate, db: Session = Depends(get_db)):
    try:
        ok = db.execute(text("SELECT ok_voice FROM sess WHERE id = :sid"), {"sid": payload.sess_id}).scalar()
        if not ok: return {"status": "skipped"}

        db.execute(text("""
            INSERT INTO stt (sess_id, speaker, s_ms, e_ms, text, conf, meta)
            VALUES (:sid, :speaker, :s_ms, :e_ms, :text, :conf, :meta)
        """), {**payload.dict(), "sid": payload.sess_id, "meta": json.dumps({"engine": "WebSpeechAPI"})})
        db.commit()
        return {"status": "saved"}
    except Exception as e:
        db.rollback(); raise HTTPException(status_code=400, detail=str(e))
    
# ---------------------------------------------------------
# 대시보드 및 알림 연동 API (이안수정_Main.html 전용)
# ---------------------------------------------------------

@app.get("/dashboard")
def get_dashboard_data(db: Session = Depends(get_db)):
    """대시보드 상단 KPI 카드 및 최근 알림 데이터를 가져옵니다."""
    try:
        # 1. 상태별 내담자 수 집계 (안정, 주의, 개선필요)
        status_stats = db.execute(text("""
            SELECT status, COUNT(*) as cnt 
            FROM client 
            GROUP BY status
        """)).mappings().all()
        
        stats_dict = {s['status']: s['cnt'] for s in status_stats}
        
        # 2. 최근 알림 리스트 (최신순 5개)
        alerts = db.execute(text("""
            SELECT a.*, c.name as client_name 
            FROM alert a
            JOIN sess s ON a.sess_id = s.id
            JOIN client c ON s.client_id = c.id
            ORDER BY a.at DESC LIMIT 5
        """)).mappings().all()

        return {
            "total_clients": sum(stats_dict.values()),
            "stable_clients": stats_dict.get("안정", 0),
            "warning_clients": stats_dict.get("주의", 0),
            "critical_clients": stats_dict.get("개선필요", 0),
            "alerts": [dict(a) for a in alerts],
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/alerts")
def get_filtered_alerts(
    alert_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sort: str = Query("desc"),
    db: Session = Depends(get_db)
):
    """이안수정_Main.html의 필터 기능에 대응하는 알림 조회 API"""
    query_str = """
        SELECT a.*, c.name as client_name 
        FROM alert a 
        JOIN sess s ON a.sess_id = s.id 
        JOIN client c ON s.client_id = c.id 
        WHERE 1=1
    """
    params = {}

    if alert_type:
        query_str += " AND a.type = :alert_type"
        params["alert_type"] = alert_type
    
    if status:
        query_str += " AND a.status = :status"
        params["status"] = status

    # 정렬 (최신순/과거순)
    query_str += f" ORDER BY a.at {sort.upper()}"
    
    result = db.execute(text(query_str), params).mappings().all()
    return {"items": [dict(r) for r in result]}

@app.patch("/api/alerts/{alert_id}/status")
def update_alert_status(alert_id: int, payload: AlertStatusUpdate, db: Session = Depends(get_db)):
    """알림 리스트에서 '확인' 버튼을 눌렀을 때 상태를 변경합니다."""
    try:
        db.execute(text("UPDATE alert SET status = :status WHERE id = :aid"), 
                   {"status": payload.status, "aid": alert_id})
        db.commit()
        return {"ok": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))



    
# [추가됨] 새로운 예약을 DB에 저장하는 API (주문 접수처)
@app.post("/appointments")
def create_appointment(payload: ApptCreateRequest, db: Session = Depends(get_db)):
    try:
        sql = """
            INSERT INTO appt (client_id, counselor_id, at, status, created_at)
            VALUES (:client_id, :counselor_id, :at, 'REQUESTED', NOW())
        """
        db.execute(text(sql), {
            "client_id": payload.client_id,
            "counselor_id": payload.counselor_id,
            "at": payload.at
        })
        db.commit() # 장부에 확정 기록
        return {"status": "success", "message": "상담 예약이 접수되었습니다."}
    except Exception as e:
        db.rollback() # 에러 발생 시 기록 취소
        raise HTTPException(status_code=400, detail=f"예약 저장 실패: {str(e)}")
    

    
# 고민 유형 저장 모델
class ClientTopicRequest(BaseModel):
    client_id: int
    topic_id: int
    prio: int  # 우선순위 (1~3)

# 1. 내담자 고민 유형 저장 (Chat_client.html 팝업에서 호출)
@app.post("/client-topics")
def save_client_topics(payload: List[ClientTopicRequest], db: Session = Depends(get_db)):
    try:
        # 기존 선택 데이터가 있다면 삭제 (최신 선택 반영)
        db.execute(text("DELETE FROM client_topic WHERE client_id = :cid"), {"cid": payload[0].client_id})
        
        for item in payload:
            db.execute(text("""
                INSERT INTO client_topic (client_id, topic_id, prio, created_at)
                VALUES (:cid, :tid, :prio, NOW())
            """), {"cid": item.client_id, "tid": item.topic_id, "prio": item.prio})
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/sessions/{sess_id}/close")
def close_session(sess_id: int, payload: SessionCloseRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)): #
    try:
        # [단계 1] 세션 상태를 'CLOSED'로 변경하고 만족도 정보를 저장합니다.
        db.execute(text("""
            UPDATE sess SET end_at = NOW(), progress = 'CLOSED', 
            end_reason = :end_reason, sat = :sat, sat_note = :sat_note
            WHERE id = :sid
        """), {
            "sid":        sess_id,
            "end_reason": payload.end_reason,
            "sat":        payload.sat,
            "sat_note":   payload.sat_note
        }) #

        # [단계 2] 기존의 내담자 등급(상태) 판별 로직을 실행합니다.
        client_row = db.execute(text(
            "SELECT client_id FROM sess WHERE id = :sid"
        ), {"sid": sess_id}).mappings().first() #

        if client_row:
            cid = client_row["client_id"]
            stats = db.execute(text("""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN end_reason = 'DROPOUT' THEN 1 ELSE 0 END) AS dropout_cnt,
                    SUM(CASE WHEN sat = 0 THEN 1 ELSE 0 END) AS unsat_cnt
                FROM sess
                WHERE client_id = :cid AND progress = 'CLOSED'
            """), {"cid": cid}).mappings().first() #

            total       = int(stats["total"] or 0)
            dropout_cnt = int(stats["dropout_cnt"] or 0)
            unsat_cnt   = int(stats["unsat_cnt"] or 0)
            dropout_rate = (dropout_cnt / total) if total > 0 else 0

            # 이탈률과 불만족 건수에 따른 상태 업데이트
            if dropout_rate >= 0.5:
                new_status = "개선필요"
            elif dropout_rate >= 0.3 or unsat_cnt > 0:
                new_status = "주의"
            else:
                new_status = "안정"

            db.execute(text(
                "UPDATE client SET status = :status WHERE id = :cid"
            ), {"status": new_status, "cid": cid}) #

        db.commit() # 여기까지의 변경 사항을 먼저 저장합니다.

        # [단계 3] 핵심 연동: 백그라운드에서 AI 분석 모델(Runner)을 가동합니다.
        def run_analysis_bg(sid: int):
            from db import SessionLocal
            from routers.api import _build_clova_client
            from routers.analysis.runner import run_core_features
            
            # 백그라운드 작업은 별도의 독립된 DB 세션을 사용해야 안전합니다.
            bg_db = SessionLocal() 
            try:
                clova = _build_clova_client()
                # runner.py의 핵심 분석 기능을 호출합니다.
                run_core_features(clova, sess_id=sid, db=bg_db)
                bg_db.commit()
            except Exception as e:
                bg_db.rollback()
                print(f"[AI 분석 에러] sess_id={sid}, error={e}")
            finally:
                bg_db.close()

        # 상담사 화면은 즉시 응답을 주고, 무거운 AI 분석은 서버 뒷단에서 처리합니다.
        background_tasks.add_task(run_analysis_bg, sess_id)

        return {"status": "closed", "sess_id": sess_id, "end_reason": payload.end_reason}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) #

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)