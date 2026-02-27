from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict

# =========================================================
# Base (Pydantic v2 대응 + Row/ORM 호환)
# =========================================================
class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# =========================================================
# ENUMs (명세서의 ENUM 고정값 반영)
# =========================================================
Speaker = Literal["COUNSELOR", "CLIENT", "SYSTEM"]  # msg.speaker :contentReference[oaicite:1]{index=1}
Channel = Literal["CHAT", "VOICE"]                  # sess.channel :contentReference[oaicite:2]{index=2}
Progress = Literal["WAITING", "ACTIVE", "CLOSED"]   # sess.progress :contentReference[oaicite:3]{index=3}
EndReason = Optional[Literal["NORMAL", "DROPOUT", "TECH", "UNKNOWN"]]  # sess.end_reason :contentReference[oaicite:4]{index=4}
AlertStatus = Literal["DETECTED", "RESOLVED"]       # alert.status :contentReference[oaicite:5]{index=5}

# alert.type 은 명세서에 VARCHAR(20) + 예시(4개)라서 Literal로 고정해도 되는데,
# 확장 가능성 남기려면 str 유지가 안전. "완벽매칭"을 최우선이면 아래 Literal 권장.
AlertType = Literal["DELAY", "SHORT", "NEG_SPIKE", "RISK_WORD"]  # alert.type 예시 :contentReference[oaicite:6]{index=6}


# =========================================================
# sess (Session)
# =========================================================
class SessionItem(APIModel):
    id: int
    uuid: str = Field(..., max_length=50)  # sess.uuid VARCHAR(50) :contentReference[oaicite:7]{index=7}
    counselor_id: int = Field(..., ge=1)
    client_id: int = Field(..., ge=1)
    appt_id: Optional[int] = Field(None, ge=1)

    channel: Channel
    progress: Progress

    start_at: datetime
    end_at: Optional[datetime] = None
    end_reason: EndReason = None

    sat: Optional[bool] = None
    sat_note: Optional[str] = Field(None, max_length=255)  # sess.sat_note VARCHAR(255) :contentReference[oaicite:8]{index=8}

    ok_text: bool
    ok_voice: bool
    ok_face: bool

    created_at: datetime


# =========================================================
# msg (Message) - 요청/응답 분리
# =========================================================
class MessageCreate(APIModel):
    sess_id: int = Field(..., ge=1)
    speaker: Speaker
    speaker_id: Optional[int] = Field(None, ge=1)
    text: Optional[str] = None
    emoji: Optional[str] = None       # DB 컬럼 추가 완료!
    file_url: Optional[str] = None    # DB 컬럼 추가 완료!
    # 명세서 NOT NULL 및 기본값 0.00 반영
    stt_conf: float = Field(default=0.00, ge=0.00, le=1.00) 

class MessageItem(APIModel):
    id: int
    sess_id: int
    speaker: Speaker
    speaker_id: Optional[int] = None
    text: Optional[str] = None
    emoji: Optional[str] = None       # 명세서 컬럼 ID 일치
    file_url: Optional[str] = None    # 명세서 컬럼 ID 일치
    stt_conf: float = Field(..., ge=0.00, le=1.00)
    at: datetime                      # 명세서 발화 시각


# =========================================================
# alert
# =========================================================
class AlertItem(APIModel):
    id: int
    sess_id: int
    msg_id: int

    type: AlertType  # 명세서 예시 4개를 고정(완벽매칭 강제) :contentReference[oaicite:11]{index=11}
    status: AlertStatus

    score: Optional[float] = Field(None, ge=0.00, le=1.00)  # alert.score 0~1 :contentReference[oaicite:12]{index=12}
    rule: Optional[str] = Field(None, max_length=50)         # alert.rule VARCHAR(50) :contentReference[oaicite:13]{index=13}
    action: Optional[str] = None
    at: datetime


# =========================================================
# quality
# =========================================================
class QualityItem(APIModel):
    id: int
    sess_id: int
    flow: float = Field(..., ge=0.00, le=100.00)   # quality.flow 0~100 :contentReference[oaicite:14]{index=14}
    score: float = Field(..., ge=0.00, le=100.00)  # quality.score 0~100 :contentReference[oaicite:15]{index=15}
    created_at: datetime


# =========================================================
# sess_analysis
# =========================================================
class SessAnalysisItem(APIModel):
    id: int
    sess_id: int
    topic_id: int
    summary: str
    note: str
    created_at: datetime
