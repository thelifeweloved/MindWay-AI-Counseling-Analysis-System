import os
import time as _time
import json
import uuid
import hashlib
import asyncio

from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import (
    Request, FastAPI, Depends, HTTPException, Query,
    WebSocket, WebSocketDisconnect, BackgroundTasks
)
from fastapi.encoders import jsonable_encoder
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text
from dotenv import load_dotenv
from starlette.websockets import WebSocketState

from db import get_db
from routers.helper import router as helper_router
from routers.deepface import analyze_face_logic
from routers.api import api_router
from routers.analysis.runner import run_core_features
from routers.analysis.clova_client import ClovaXClient

load_dotenv()
app = FastAPI(title="Mindway Post-Analysis API", version="1.1.2")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "frontend_test")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.mount("/frontend_test", StaticFiles(directory=STATIC_DIR), name="frontend_test")
    
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(helper_router)
app.include_router(api_router)


@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def chrome_devtools_well_known():
    """Chrome DevTools가 요청하는 경로 — 404 방지용 빈 JSON 반환"""
    return {}

# ---------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------
class LoginRequest(BaseModel):
    email: str
    pwd: str

class ClientLoginRequest(BaseModel):
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
    ok_face:  Optional[bool] = None

class QualityCreate(BaseModel):
    flow:  float = Field(..., ge=0.0, le=100.0)
    score: float = Field(..., ge=0.0, le=100.0)

class SessionCloseRequest(BaseModel):
    end_reason: str  = Field("NORMAL", pattern="^(NORMAL|DROPOUT|TECH|UNKNOWN)$")
    sat:         Optional[int] = Field(None, ge=0, le=1)
    sat_note:   Optional[str] = None

class NoteUpdateRequest(BaseModel):
    topic_id: Optional[int] = Field(1, ge=1)
    note: str

class ApptUpdateRequest(BaseModel):
    counselor_id: Optional[int] = None
    status: Optional[str] = None

class ApptCreateRequest(BaseModel):
    client_id: int

class ClientStartSessionRequest(BaseModel):
    client_id: int
    counselor_id: int
    appt_id: Optional[int] = None  # 추가

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
# Auth
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

# ---------------------------------------------------------
# Matching & Sessions
# ---------------------------------------------------------
@app.post("/client/request-appt")
def request_client_appointment(payload: ApptCreateRequest, db: Session = Depends(get_db)):
    """내담자가 대기 화면 진입 시 예약을 'REQUESTED'로 자동 생성"""
    existing = db.execute(text("""
        SELECT id FROM appt 
        WHERE client_id = :cid AND status IN ('REQUESTED', 'CONFIRMED')
        ORDER BY id DESC LIMIT 1
    """), {"cid": payload.client_id}).scalar()
    
    if existing:
        return {"status": "success", "appt_id": existing}
        
    res = db.execute(text("""
        INSERT INTO appt (client_id, status, at)
        VALUES (:cid, 'REQUESTED', NOW())
    """), {"cid": payload.client_id})
    db.commit()
    return {"status": "success", "appt_id": res.lastrowid}

@app.get("/client/{client_id}/my-appointment")
def get_client_my_appointment(client_id: int, db: Session = Depends(get_db)):
    """내담자가 채팅방에 들어가기 전, 자신에게 매칭된 상담사 번호를 확인하는 API"""
    sql = """
        SELECT id AS appt_id, counselor_id, status, at
        FROM appt
        WHERE client_id = :cid AND counselor_id IS NOT NULL 
        ORDER BY at DESC LIMIT 1
    """
    appt = db.execute(text(sql), {"cid": client_id}).mappings().first()
    
    if not appt:
        raise HTTPException(status_code=404, detail="아직 배정된 상담사 또는 예약이 없습니다.")
        
    return {"status": "success", "data": dict(appt)}

@app.post("/client/start-session")
def client_start_session(payload: ClientStartSessionRequest, db: Session = Depends(get_db)):
    """
    내담자와 상담사가 동일한 세션 ID를 공유하도록 매칭 로직을 강화합니다.
    """
    coid = payload.counselor_id
    clid = payload.client_id
    appt_id = payload.appt_id

    # 1. 예약 ID(appt_id)가 있는 경우: 해당 예약에 연결된 기존 세션이 있는지 확인
    if appt_id:
        existing = db.execute(text("""
            SELECT id FROM sess 
            WHERE appt_id = :appt_id 
              AND progress IN ('WAITING','ACTIVE')
              AND end_at IS NULL
            ORDER BY id DESC LIMIT 1
        """), {"appt_id": appt_id}).scalar()
        
        if existing:
            # 이미 생성된 세션이 있다면 해당 ID를 그대로 반환 (상담사/내담자 동기화)
            return {"status": "success", "sess_id": int(existing), "reused": True}

    # 2. 예약 ID가 없더라도 동일한 상담사-내담자 조합의 진행 중인 세션이 있는지 확인
    existing_no_appt = db.execute(text("""
        SELECT id FROM sess
        WHERE client_id = :clid AND counselor_id = :coid
          AND end_at IS NULL AND progress IN ('WAITING','ACTIVE')
        ORDER BY id DESC LIMIT 1
    """), {"clid": clid, "coid": coid}).scalar()
    
    if existing_no_appt:
        return {"status": "success", "sess_id": int(existing_no_appt), "reused": True}

    # 3. 위 조건에 해당하지 않는 경우에만 새 세션 생성
    new_uuid = str(uuid.uuid4())
    res = db.execute(text("""
        INSERT INTO sess (uuid, counselor_id, client_id, appt_id, channel, progress)
        VALUES (:uuid, :coid, :clid, :appt_id, 'CHAT', 'ACTIVE')
    """), {
        "uuid": new_uuid, 
        "coid": coid, 
        "clid": clid, 
        "appt_id": appt_id
    })
    db.commit()
    
    return {"status": "success", "sess_id": int(res.lastrowid), "reused": False}

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

@app.get("/sessions/{sess_id}")
def get_session(sess_id: int, db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT
            id, uuid, counselor_id, client_id, appt_id, channel,
            progress, start_at, end_at, end_reason, sat, sat_note
        FROM sess
        WHERE id = :sid LIMIT 1
    """), {"sid": sess_id}).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="세션 없음")

    progress = row["progress"]
    is_closed = (progress == "CLOSED") or (row["end_at"] is not None)

    return {
        "sess_id": int(row["id"]),
        "uuid": row["uuid"],
        "counselor_id": row["counselor_id"],
        "client_id": row["client_id"],
        "appt_id": row["appt_id"],
        "channel": row["channel"],
        "progress": progress,
        "status": progress,
        "start_at": row["start_at"],
        "end_at": row["end_at"],
        "end_reason": row["end_reason"],
        "sat": row["sat"],
        "sat_note": row["sat_note"],
        "is_closed": bool(is_closed),
    }

@app.get("/sessions/{sess_id}/status")
def get_session_status(sess_id: int, db: Session = Depends(get_db)):
    return get_session(sess_id, db)

# ---------------------------------------------------------
# Messages & Alerts
# ---------------------------------------------------------
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

# ---------------------------------------------------------
# Dashboard & Stats
# ---------------------------------------------------------


@app.get("/sessions/{sess_id}/faces")
def session_faces(sess_id: int, db: Session = Depends(get_db)):
    """DeepFace(face) 로그 조회 - 상담사 폴링 fallback용 (시간 오름차순)"""
    rows = db.execute(text("""
        SELECT id, at AS created_at, label, score
        FROM face
        WHERE sess_id = :sid
        ORDER BY at ASC, id ASC
    """), {"sid": sess_id}).mappings().all()
    return {"items": jsonable_encoder(list(rows))}

# ---------------------------------------------------------
# Dashboard & Stats
# ---------------------------------------------------------


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

    # 내담자가 선택한 고민 주제 (SessionDetail.html client_topics 섹션용)
    client_topics_rows = db.execute(text("""
        SELECT t.id, t.name, t.code, st.prio
        FROM sess_topic st
        JOIN topic t ON st.topic_id = t.id
        WHERE st.sess_id = :sid
        ORDER BY st.prio ASC
    """), {"sid": sess_id}).mappings().all()

    total_alerts = int(db.execute(text("SELECT COUNT(*) FROM alert WHERE sess_id = :sid"), {"sid": sess_id}).scalar() or 0)
    alert_types_rows = db.execute(text("""
        SELECT type, COUNT(*) AS cnt
        FROM alert WHERE sess_id = :sid
        GROUP BY type ORDER BY cnt DESC
    """), {"sid": sess_id}).mappings().all()
    alert_types = [{"type": r["type"], "cnt": int(r["cnt"])} for r in alert_types_rows]

    quality = {"flow": 0.0, "score": 0.0, "churn_prob": risk_score}
    try:
        quality_row = db.execute(
            text("SELECT flow, score FROM quality WHERE sess_id = :sid LIMIT 1"),
            {"sid": sess_id},
        ).mappings().first()
        if quality_row:
            quality["flow"] = float(quality_row["flow"] or 0)
            quality["score"] = float(quality_row["score"] or 0)
    except Exception:
        pass

    return {
        "session": jsonable_encoder(sess),
        "risk_score": risk_score,
        "topic_analysis": jsonable_encoder(topic_analysis),
        "client_topics": jsonable_encoder(list(client_topics_rows)),
        "risk_label": "HIGH" if risk_score >= 0.7 else "MID" if risk_score >= 0.4 else "LOW",
        "alert_summary": {"total_alerts": total_alerts},
        "alert_types": alert_types,
        "quality": quality
    }

@app.get("/stats/topic-dist")
def topic_dist(counselor_id: int = Query(..., ge=1), db: Session = Depends(get_db)):
    sql = """
        SELECT t.name AS topic_name, t.code AS topic_code, COUNT(sa.sess_id) AS total
        FROM topic t
        JOIN sess_analysis sa ON t.id = sa.topic_id
        JOIN sess s ON sa.sess_id = s.id
        WHERE s.counselor_id = :cid
        GROUP BY t.id ORDER BY total DESC
    """
    return {"items": jsonable_encoder(list(db.execute(text(sql), {"cid": counselor_id}).mappings().all()))}

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
    sql = """
        SELECT c.status AS client_grade, COUNT(*) AS total
        FROM client c
        JOIN sess s ON s.client_id = c.id
        WHERE s.counselor_id = :cid
        GROUP BY c.status
        ORDER BY total DESC
    """
    return {"items": jsonable_encoder(list(db.execute(text(sql), {"cid": counselor_id}).mappings().all()))}

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

# ---------------------------------------------------------
# Appointments & Counselors
# ---------------------------------------------------------
@app.post("/appointments")
def create_appointment(payload: dict, db: Session = Depends(get_db)):
    """Login_client.html에서 상담사 선택 후 예약 생성"""
    try:
        client_id     = payload.get("client_id")
        counselor_id  = payload.get("counselor_id")
        at            = payload.get("at")
        status        = payload.get("status", "CONFIRMED")
        if not client_id or not counselor_id:
            raise HTTPException(status_code=400, detail="client_id, counselor_id 필수")
        res = db.execute(text("""
            INSERT INTO appt (client_id, counselor_id, at, status)
            VALUES (:cid, :couid, :at, :status)
        """), {"cid": client_id, "couid": counselor_id, "at": at, "status": status})
        db.commit()
        return {"status": "success", "appt_id": res.lastrowid}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/appointments")
def get_appointments(counselor_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    sql = """
        SELECT a.id, a.client_id, a.counselor_id, c.name AS client_name, a.at, a.status, a.created_at
        FROM appt a 
        JOIN client c ON a.client_id = c.id 
        WHERE (:cid IS NULL OR a.counselor_id = :cid) 
        ORDER BY a.at ASC
    """
    result = db.execute(text(sql), {"cid": counselor_id}).mappings().all()
    return {"items": jsonable_encoder(list(result))}

@app.get("/counselors")
def get_counselors(db: Session = Depends(get_db)):
    sql = "SELECT id, name FROM counselor"
    result = db.execute(text(sql)).mappings().all()
    return {"items": jsonable_encoder(list(result))}


@app.post("/appt")
def create_appt(payload: dict, db: Session = Depends(get_db)):
    """
    내담자가 상담사·날짜·시간 선택 후 예약 생성.
    A안: 접수 없이 바로 CONFIRMED 저장 → 상담사 대시보드에 즉시 확정 상태로 표시.
    """
    cid  = payload.get("client_id")
    coid = payload.get("counselor_id")
    at   = payload.get("at")
    if not (cid and coid and at):
        raise HTTPException(status_code=400, detail="client_id, counselor_id, at 필수")

    res = db.execute(text("""
        INSERT INTO appt (client_id, counselor_id, at, status)
        VALUES (:cid, :coid, :at, 'CONFIRMED')
    """), {"cid": cid, "coid": coid, "at": at})
    db.commit()
    return {"ok": True, "appt_id": res.lastrowid}

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
# Topic APIs (필터링 및 통합 저장 로직 적용)
# ---------------------------------------------------------
@app.get("/topics")
def get_topics(db: Session = Depends(get_db)):
    """내담자 고민 유형 선택지 반환 — REGISTER 타입만, 고정 순서로 제공"""
    rows = db.execute(text("""
        SELECT id, code, name FROM topic
        WHERE type = 'REGISTER'
        ORDER BY FIELD(code,
            'ANXIETY', 'DEPRESSION', 'RELATION', 'FAMILY',
            'ROMANCE', 'CAREER', 'WORK', 'TRAUMA', 'SELF_ESTEEM', 'ETC')
    """)).mappings().all()
    return {"items": [dict(r) for r in rows]}

@app.post("/sessions/{sess_id}/topics")
def save_session_topics(sess_id: int, payload: dict, db: Session = Depends(get_db)):

    topic_ids: List[int] = payload.get("topic_ids", [])

    if not topic_ids:
        raise HTTPException(status_code=400, detail="topic_ids가 비어있습니다.")

    for idx, tid in enumerate(topic_ids):
        db.execute(text("""
            INSERT INTO sess_topic (sess_id, topic_id, prio)
            VALUES (:sid, :tid, :prio)
            ON DUPLICATE KEY UPDATE prio = :prio
        """), {"sid": sess_id, "tid": tid, "prio": idx + 1})

    db.commit()
    return {"ok": True}

# ---------------------------------------------------------
# Analysis & Core Functions
# ---------------------------------------------------------
@app.patch("/sessions/{sess_id}/analysis")
def update_analysis_note(sess_id: int, payload: NoteUpdateRequest, db: Session = Depends(get_db)):
    try:
        existing_row = db.execute(text("""
            SELECT id, topic_id FROM sess_analysis WHERE sess_id = :sid LIMIT 1
        """), {"sid": sess_id}).mappings().first()

        if existing_row:
            actual_tid = existing_row["topic_id"]
            db.execute(text("""
                UPDATE sess_analysis SET note = :note WHERE sess_id = :sid AND topic_id = :tid
            """), {"note": payload.note, "sid": sess_id, "tid": actual_tid})
        else:
            actual_tid = payload.topic_id or 1
            db.execute(text("""
                INSERT INTO sess_analysis (sess_id, topic_id, summary, note)
                VALUES (:sid, :tid, '', :note)
            """), {"note": payload.note, "sid": sess_id, "tid": actual_tid})
            
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

@app.post("/sessions/{sess_id}/close")
async def close_session(sess_id: int, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        raw = await request.body()
        body_json = json.loads(raw) if raw else {}
    except Exception:
        body_json = {}
    
    payload = SessionCloseRequest(
        end_reason = body_json.get("end_reason", "NORMAL"),
        sat        = body_json.get("sat"),
        sat_note   = body_json.get("sat_note"),
    )
    
    try:
        db.execute(text("""
            UPDATE sess SET end_at = NOW(), progress = 'CLOSED', 
            end_reason = :end_reason, sat = :sat, sat_note = :sat_note
            WHERE id = :sid
        """), {
            "sid":        sess_id,
            "end_reason": payload.end_reason,
            "sat":        payload.sat,
            "sat_note":   payload.sat_note
        })

        client_row = db.execute(text(
            "SELECT client_id FROM sess WHERE id = :sid"
        ), {"sid": sess_id}).mappings().first()

        if client_row:
            cid = client_row["client_id"]
            stats = db.execute(text("""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN end_reason = 'DROPOUT' THEN 1 ELSE 0 END) AS dropout_cnt,
                    SUM(CASE WHEN sat = 0 THEN 1 ELSE 0 END) AS unsat_cnt
                FROM sess
                WHERE client_id = :cid AND progress = 'CLOSED'
            """), {"cid": cid}).mappings().first()

            total = int(stats["total"] or 0)
            dropout_rate = (int(stats["dropout_cnt"] or 0) / total) if total > 0 else 0
            unsat_cnt = int(stats["unsat_cnt"] or 0)

            new_status = "안정"
            if dropout_rate >= 0.5: new_status = "개선필요"
            elif dropout_rate >= 0.3 or unsat_cnt > 0: new_status = "주의"

            db.execute(text("UPDATE client SET status = :status WHERE id = :cid"), {"status": new_status, "cid": cid})

        # face 로그는 세션 종료 시 일괄 저장
        try:
            _flush_face_buffer(db, sess_id)
        except Exception:
            pass

        db.commit()

        # ✅ 수정된 백그라운드 작업 (들여쓰기 및 저장 로직 통합 완료)
        def run_ai_background(sid: int):
            db_gen = get_db()
            bg_db = next(db_gen)
            try:
                # 1. 클라이언트 생성 (환경변수 기반)
                clova = ClovaXClient(
                    api_key=os.getenv("CLOVA_API_KEY", ""), 
                    endpoint_id=os.getenv("CLOVA_ENDPOINT_ID", "")
                )
                # 2. 핵심 분석 실행 (runner.py 호출)
                run_core_features(clova, sess_id=sid, db=bg_db)
                
                # 3. [치명적 수정] 분석 결과를 실제 DB 디스크에 기록 확정!
                bg_db.commit()  
                
            except Exception as e_run:
                # 4. 에러 발생 시 작업 취소 (데이터 꼬임 방지)
                bg_db.rollback() 
                print(f"[runner 백그라운드 실패] {e_run}")
            finally:
                bg_db.close()

        background_tasks.add_task(run_ai_background, sess_id)
        return {"status": "closed", "sess_id": sess_id}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# ---------------------------------------------------------
# WebSocket & Heartbeat (이안님의 고유 기능 유지)
# ---------------------------------------------------------
_face_prev_scores: dict = {}
_face_last_analyze: dict = {}   # session_id → 마지막 분석 시각
FACE_CHANGE_THRESHOLD = 0.2
FACE_ANALYZE_INTERVAL = 1.0     # 서버 분석 주기 (초)
_face_buffer: dict = {}       # sess_db_id(int) -> list[dict] (bulk insert buffer)
_ok_face_cache: dict = {}     # sess_db_id(int) -> bool (consent cache)
_viewer_ws: dict = {}  # sess_id → 상담사 WebSocket (영상 중계용)
_heartbeat_store: dict = {}
_last_face_saved: dict = {} 
_signal_peers: dict = {}


def _ok_face_cached(db: Session, sess_db_id: int) -> bool:
    """ok_face 동의는 세션당 1회만 DB 조회하고 캐시에 저장"""
    if sess_db_id in _ok_face_cache:
        return bool(_ok_face_cache[sess_db_id])
    try:
        ok = db.execute(text("SELECT ok_face FROM sess WHERE id = :sid"), {"sid": int(sess_db_id)}).scalar()
        okb = bool(ok)
    except Exception:
        okb = False
    _ok_face_cache[sess_db_id] = okb
    return okb

def _flush_face_buffer(db: Session, sess_db_id: int) -> int:
    """_face_buffer에 쌓인 face 로그를 세션 종료 시 일괄 INSERT"""
    rows = _face_buffer.get(int(sess_db_id)) or []
    if not rows:
        return 0
    # 동의 없으면 저장 스킵 + 버퍼만 비움
    if not _ok_face_cached(db, int(sess_db_id)):
        _face_buffer.pop(int(sess_db_id), None)
        return 0

    sql = text(
        "INSERT INTO face (sess_id, at, label, score, dist, meta) "
        "VALUES (:sid, :at, :l, :s, :d, :meta)"
    )
    try:
        db.execute(sql, rows)  # executemany
        # 커밋은 호출자(close_session)가 수행
        inserted = len(rows)
    except Exception:
        inserted = 0
        db.rollback()
    finally:
        _face_buffer.pop(int(sess_db_id), None)
    return inserted

def should_store_face(session_id: str, dominant: str, score: float, now: float) -> bool:
    prev = _last_face_saved.get(session_id)
    score = float(score or 0.0)

    prev = _last_face_saved.get(session_id)

    if prev is None:
        _last_face_saved[session_id] = {
            "dominant": dominant,
            "score": score,
            "ts": now,
        }
        return True

    # 감정 라벨이 바뀌면 저장
    if prev["dominant"] != dominant:
        _last_face_saved[session_id] = {
            "dominant": dominant,
            "score": score,
            "ts": now,
        }
        return True

    # 같은 감정이어도 점수 변화가 크면 저장
    if abs(float(prev["score"]) - float(score)) >= 0.15:
        _last_face_saved[session_id] = {
            "dominant": dominant,
            "score": score,
            "ts": now,
        }
        return True

    # 너무 오래 같은 상태면 10초마다 1회 저장
    if (now - float(prev["ts"])) >= 10.0:
        _last_face_saved[session_id] = {
            "dominant": dominant,
            "score": score,
            "ts": now,
        }
        return True

    return False


@app.post("/sessions/{sess_id}/reactivate")
def reactivate_session(sess_id: int, db: Session = Depends(get_db)):
    """새로고침으로 인한 DROPOUT을 취소하고 세션을 ACTIVE로 복구"""
    row = db.execute(
        text("SELECT progress, end_reason FROM sess WHERE id = :sid"),
        {"sid": sess_id}
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="세션 없음")

    if row["progress"] == "CLOSED" and row["end_reason"] == "DROPOUT":
        db.execute(text("""
            UPDATE sess SET progress = 'ACTIVE', end_at = NULL, end_reason = NULL
            WHERE id = :sid
        """), {"sid": sess_id})
        db.commit()
        _heartbeat_store[sess_id] = _time.time()
        return {"ok": True, "restored": True}

    _heartbeat_store[sess_id] = _time.time()
    return {"ok": True, "restored": False}

@app.post("/sessions/{sess_id}/heartbeat")
def session_heartbeat(sess_id: int, db: Session = Depends(get_db)):
    _heartbeat_store[sess_id] = _time.time()
    return {"ok": True}

@app.get("/sessions/{sess_id}/heartbeat-check")
def heartbeat_check(sess_id: int, db: Session = Depends(get_db)):
    last = _heartbeat_store.get(sess_id)
    if last is None:
        return {"alive": None}
    elapsed = _time.time() - last

    if elapsed > 300:
        try:
            db.execute(text("""
                UPDATE sess SET end_at = NOW(), progress = 'CLOSED', end_reason = 'DROPOUT'
                WHERE id = :sid AND progress = 'ACTIVE'
            """), {"sid": sess_id})
            db.commit()
            _heartbeat_store.pop(sess_id, None)
            return {"alive": False, "auto_closed": True, "elapsed": round(elapsed)}
        except Exception as e:
            db.rollback()
            print(f"Heartbeat 5분 타임아웃 처리 에러: {e}")

    return {"alive": elapsed <= 15, "elapsed": round(elapsed)}
            

@app.websocket("/ws/analyze/{session_id}")
async def websocket_analyze(websocket: WebSocket, session_id: str, db: Session = Depends(get_db)):
    """내담자 프레임(base64)을 받아 표정 보조지표 분석 → ws/view로 push + _face_buffer에 누적"""
    print(f"[analyze] connect requested | session_id={session_id}")

    try:
        await websocket.accept()
        print(f"[analyze] accepted | session_id={session_id}")

        while True:
            raw = await websocket.receive_text()
            print(f"[analyze] received raw text | session_id={session_id} | length={len(raw) if raw else 0}")

            try:
                payload = json.loads(raw) if raw else {}
            except Exception as e:
                print(f"[analyze] json parse error | session_id={session_id} | error={repr(e)}")
                payload = {}

            image_b64 = payload.get("image_base64")
            sess_db_id = payload.get("sess_db_id")

            if not image_b64 or sess_db_id is None:
                print(f"[analyze] invalid payload | session_id={session_id} | sess_db_id={sess_db_id} | has_image={bool(image_b64)}")
                continue

            now = _time.time()
            last = _face_last_analyze.get(session_id, 0.0)
            if (now - last) < float(FACE_ANALYZE_INTERVAL):
                print(f"[analyze] skipped by interval | session_id={session_id} | delta={now - last:.3f}")
                continue

            _face_last_analyze[session_id] = now

            try:
                result = await asyncio.to_thread(analyze_face_logic, session_id, image_b64)
                ui = result.get("ui") or {}
                print(
                    f"[analyze] analysis result | session_id={session_id} "
                    f"| status={result.get('status')} "
                    f"| ui_label={ui.get('label')} "
                    f"| ui_score={ui.get('score')}"
                )
            except Exception as e:
                print(f"[analyze] analyze_face_logic error | session_id={session_id} | error={repr(e)}")
                continue

            viewer = _viewer_ws.get(str(session_id)) or _viewer_ws.get(session_id)
            if viewer and viewer.client_state == WebSocketState.CONNECTED:
                try:
                    await viewer.send_text(json.dumps({"type": "emotion", "result": result}))
                    print(f"[analyze] pushed to viewer | session_id={session_id}")
                except Exception as e:
                    print(f"[analyze] viewer send error | session_id={session_id} | error={repr(e)}")
                    _viewer_ws.pop(str(session_id), None)
                    _viewer_ws.pop(session_id, None)

            if result.get("status") == "success":
                try:
                    sid_int = int(sess_db_id)
                except Exception as e:
                    print(f"[analyze] sess_db_id int cast error | session_id={session_id} | sess_db_id={sess_db_id} | error={repr(e)}")
                    continue

                ui = result.get("ui") or {}
                label = ui.get("label") or result.get("dominant") or "neutral"
                score = float(ui.get("score", result.get("score", 0.0)) or 0.0)
                dist3 = result.get("dist3") or {
                    "positive": 0.0,
                    "neutral": 1.0,
                    "caution": 0.0,
                }
                meta = result.get("meta") or {}
                meta["engine"] = "deepface_ws"
                meta["version"] = "1.2"

                try:
                    if _ok_face_cached(db, sid_int):
                        if should_store_face(str(session_id), label, score, now):
                            row = {
                                "sid": sid_int,
                                "at": datetime.utcnow(),
                                "l": label,
                                "s": round(score, 3),
                                "d": json.dumps(dist3, ensure_ascii=False),
                                "meta": json.dumps(meta, ensure_ascii=False),
                            }
                            _face_buffer.setdefault(sid_int, []).append(row)
                            print(f"[analyze] buffered face row | session_id={session_id} | sid={sid_int} | label={label} | score={score:.3f}")
                        else:
                            print(f"[analyze] skipped store by policy | session_id={session_id} | sid={sid_int}")
                    else:
                        print(f"[analyze] ok_face false | session_id={session_id} | sid={sid_int}")
                except Exception as e:
                    print(f"[analyze] face buffer/store error | session_id={session_id} | sid={sid_int} | error={repr(e)}")

                _face_prev_scores[session_id] = score

    except WebSocketDisconnect:
        print(f"[analyze] disconnected | session_id={session_id}")
    except Exception as e:
        print(f"[analyze] outer error | session_id={session_id} | error={repr(e)}")
    finally:
        print(f"[analyze] cleanup | session_id={session_id}")
        _face_prev_scores.pop(session_id, None)
        _face_last_analyze.pop(session_id, None)
        _last_face_saved.pop(session_id, None)

@app.websocket("/ws/signal/{session_id}/{role}")
async def websocket_signal(websocket: WebSocket, session_id: str, role: str):
    """WebRTC 시그널링: offer / answer / ICE candidate relay"""
    print(f"[signal] connect requested | session_id={session_id} | role={role}")

    try:
        await websocket.accept()
        print(f"[signal] accepted | session_id={session_id} | role={role}")

        if session_id not in _signal_peers:
            _signal_peers[session_id] = {}

        _signal_peers[session_id][role] = websocket
        print(f"[signal] peer registered | session_id={session_id} | role={role} | peers={list(_signal_peers[session_id].keys())}")

        peer_role = "counselor" if role == "client" else "client"

        while True:
            msg = await websocket.receive_text()
            print(f"[signal] received message | session_id={session_id} | role={role} | length={len(msg) if msg else 0}")

            peer = _signal_peers.get(session_id, {}).get(peer_role)

            if peer and peer.client_state == WebSocketState.CONNECTED:
                try:
                    await peer.send_text(msg)
                    print(f"[signal] relayed message | session_id={session_id} | from={role} | to={peer_role}")
                except Exception as e:
                    print(f"[signal] relay error | session_id={session_id} | from={role} | to={peer_role} | error={repr(e)}")
                    _signal_peers.get(session_id, {}).pop(peer_role, None)
            else:
                print(f"[signal] peer not connected | session_id={session_id} | from={role} | expected_peer={peer_role}")

    except WebSocketDisconnect:
        print(f"[signal] disconnected | session_id={session_id} | role={role}")
    except Exception as e:
        print(f"[signal] outer error | session_id={session_id} | role={role} | error={repr(e)}")
    finally:
        if session_id in _signal_peers:
            _signal_peers[session_id].pop(role, None)
            if not _signal_peers[session_id]:
                _signal_peers.pop(session_id, None)
        print(f"[signal] cleanup | session_id={session_id} | role={role}")

@app.websocket("/ws/view/{session_id}")
async def websocket_view(websocket: WebSocket, session_id: str):
    """상담사가 연결 → 내담자 프레임/감정 결과를 실시간 수신"""
    print(f"[view] connect requested | session_id={session_id}")

    try:
        await websocket.accept()
        print(f"[view] accepted | session_id={session_id}")

        _viewer_ws[session_id] = websocket
        print(f"[view] viewer registered | session_id={session_id}")

        while True:
            msg = await websocket.receive_text()
            print(f"[view] keepalive/message | session_id={session_id} | length={len(msg) if msg else 0}")

    except WebSocketDisconnect:
        print(f"[view] disconnected | session_id={session_id}")
    except Exception as e:
        print(f"[view] outer error | session_id={session_id} | error={repr(e)}")
    finally:
        _viewer_ws.pop(session_id, None)
        print(f"[view] cleanup | session_id={session_id}")

@app.post("/face/save")
def save_face(payload: FaceSaveRequest, db: Session = Depends(get_db)):
    try:
        ok = db.execute(text("SELECT ok_face FROM sess WHERE id = :sid"), {"sid": payload.sess_id}).scalar()
        if not ok: return {"status": "skipped"}
        db.execute(text("INSERT INTO face (sess_id, at, label, score, dist, meta) VALUES (:sid, NOW(), :l, :s, :d, :meta)"),
                   {"sid": payload.sess_id, "l": payload.label, "s": payload.score, "d": json.dumps(payload.dist), "meta": json.dumps({"engine": "deepface_http", "version": "1.0"})})
        db.commit()
        return {"status": "saved"}
    except Exception as e:
        db.rollback(); raise HTTPException(status_code=400, detail=str(e))


class HttpAnalyzeRequest(BaseModel):
    session_id: str
    image_base64: str
    sess_db_id: Optional[int] = None

@app.post("/analyze")
async def http_analyze(payload: HttpAnalyzeRequest, db: Session = Depends(get_db)):
    result = await asyncio.to_thread(analyze_face_logic, payload.session_id, payload.image_base64)
    if result.get("status") == "success" and payload.sess_db_id:
        ui = result.get("ui") or {}
        dominant = ui.get("label") or result.get("dominant") or "neutral"
        score = float(ui.get("score", result.get("score", 0.0)) or 0.0)
        dist = result.get("dist3") or {"positive": 0.0, "neutral": 1.0, "caution": 0.0}
        prev = _face_prev_scores.get(payload.session_id)
        if prev is None or abs(score - prev) >= FACE_CHANGE_THRESHOLD:
            try:
                ok = db.execute(text("SELECT ok_face FROM sess WHERE id = :sid"), {"sid": int(payload.sess_db_id)}).scalar()
                if ok:
                    db.execute(
                        text("INSERT INTO face (sess_id, at, label, score, dist, meta) VALUES (:sid, NOW(), :l, :s, :d, :meta)"),
                        {
                            "sid": int(payload.sess_db_id),
                            "l": dominant,
                            "s": round(score, 2),
                            "d": json.dumps(dist, ensure_ascii=False),
                            "meta": json.dumps(result.get("meta") or {"engine": "deepface_http", "version": "1.2"}, ensure_ascii=False),
                        }
                    )
                    db.commit()
            except Exception:
                db.rollback()
        _face_prev_scores[payload.session_id] = score
    return result


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
    row = db.execute(text("SELECT ok_text, ok_face FROM sess WHERE id = :sid"), {"sid": sess_id}).mappings().first()
    if not row: raise HTTPException(status_code=404, detail="세션 없음")
    return {"ok_text": bool(row["ok_text"]), "ok_face": bool(row["ok_face"])}

@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    try:
        v = db.execute(text("SELECT 1")).scalar()
        return {"db": "ok", "ping": v, "port": 3307}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB Connection Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)