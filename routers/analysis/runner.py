# routers/analysis_services/runner.py
# ✅ pymysql 직접 연결 제거 → SQLAlchemy Session으로 완전 통일
import json
import logging
from typing import Any, Dict, List

from sqlalchemy.orm import Session
from sqlalchemy import text

from .session_repo import load_dialog_text, load_msg_rows
from .feature2 import analyze_feature2
from .feature3 import analyze_feature3
from .feature4 import analyze_feature4

try:
    from .feature1 import analyze_feature1_for_alert_rows
except Exception:
    from feature1 import analyze_feature1_for_alert_rows

logger = logging.getLogger("uvicorn.error")


def _json_dumps_safe(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return json.dumps({"_fallback": str(obj)}, ensure_ascii=False)


# ──────────────────────────────────────────
# DB 저장 함수들 (모두 SQLAlchemy Session 사용)
# ──────────────────────────────────────────

def insert_text_emotions(db: Session, emotion_items: List[Dict[str, Any]]) -> None:
    rows = [x for x in emotion_items if x.get("msg_id") is not None]
    if not rows:
        return

    msg_ids = [int(x["msg_id"]) for x in rows]
    placeholders = ",".join([str(mid) for mid in msg_ids])
    db.execute(text(f"DELETE FROM text_emotion WHERE msg_id IN ({placeholders})"))

    for item in rows:
        label = str(item.get("label", "neutral")).strip().lower() or "neutral"
        score = item.get("score", 0.5)
        try:
            score = float(score)
        except Exception:
            score = 0.5
        score = round(max(0.0, min(1.0, score)), 4)
        meta_obj = item.get("meta") or {"source": "feature3"}

        db.execute(
            text("""
                INSERT INTO text_emotion (msg_id, label, score, meta)
                VALUES (:msg_id, :label, :score, :meta)
            """),
            {
                "msg_id": int(item["msg_id"]),
                "label": label,
                "score": score,
                "meta": _json_dumps_safe(meta_obj),
            },
        )


def upsert_sess_analysis(db: Session, *, sess_id: int, topic_id: int, summary: str, note: str) -> None:
    db.execute(
        text("""
            INSERT INTO sess_analysis (sess_id, topic_id, summary, note)
            VALUES (:sess_id, :topic_id, :summary, :note)
            ON DUPLICATE KEY UPDATE
                summary = VALUES(summary),
                note    = VALUES(note)
        """),
        {
            "sess_id": int(sess_id),
            "topic_id": int(topic_id),
            "summary": summary,
            "note": note,
        },
    )


def upsert_quality(db: Session, *, sess_id: int, flow: float, score: float) -> None:
    try:
        flow = float(flow)
    except Exception:
        flow = 50.0
    try:
        score = float(score)
    except Exception:
        score = 50.0

    flow = round(max(0.0, min(100.0, flow)), 2)
    score = round(max(0.0, min(100.0, score)), 2)

    db.execute(
        text("""
            INSERT INTO quality (sess_id, flow, score)
            VALUES (:sess_id, :flow, :score)
            ON DUPLICATE KEY UPDATE
                flow  = VALUES(flow),
                score = VALUES(score)
        """),
        {"sess_id": int(sess_id), "flow": flow, "score": score},
    )


def insert_alert_rows(db: Session, alert_rows: List[Dict[str, Any]]) -> None:
    rows = [r for r in alert_rows if r.get("sess_id") is not None and r.get("msg_id") is not None]
    if not rows:
        return

    sess_id = int(rows[0]["sess_id"])
    alert_type = str(rows[0].get("type", "")).strip() or "CONTINUITY_SIGNAL"

    db.execute(
        text("DELETE FROM alert WHERE sess_id = :sess_id AND type = :type"),
        {"sess_id": sess_id, "type": alert_type},
    )

    has_at = all(("at" in r and r["at"] is not None) for r in rows)

    for r in rows:
        params = {
            "sess_id": int(r["sess_id"]),
            "msg_id": int(r["msg_id"]),
            "type": str(r.get("type", alert_type)),
            "status": str(r.get("status", "DETECTED")),
            "score": float(r.get("score", 0.0)),
            "rule": str(r.get("rule", "LOW")),
            # ✅ action: NOT NULL 컬럼 대비 빈 문자열로 저장
            "action": str(r.get("action", "")),
        }

        if has_at:
            params["at"] = str(r.get("at"))
            db.execute(
                text("""
                    INSERT INTO alert (sess_id, msg_id, type, status, score, rule, action, at)
                    VALUES (:sess_id, :msg_id, :type, :status, :score, :rule, :action, :at)
                """),
                params,
            )
        else:
            db.execute(
                text("""
                    INSERT INTO alert (sess_id, msg_id, type, status, score, rule, action)
                    VALUES (:sess_id, :msg_id, :type, :status, :score, :rule, :action)
                """),
                params,
            )


# ──────────────────────────────────────────
# 메인 파이프라인
# ──────────────────────────────────────────

def run_core_features(
    clova_client,
    *,
    sess_id: int,
    db: Session,          # ✅ DB 연결을 외부(api.py)에서 주입받음
) -> dict:
    """
    1) 데이터 로드 (session_repo, SQLAlchemy)
    2) LLM 분석 (feature1~4)
    3) DB 저장 (SQLAlchemy, 트랜잭션은 api.py의 get_db()가 관리)
    """

    # ── 1) 데이터 로드 ──────────────────────
    dialog_text = load_dialog_text(db, sess_id)
    msg_rows = load_msg_rows(db, sess_id)

    # ── 2) LLM 분석 ─────────────────────────
    f1_alert_rows = analyze_feature1_for_alert_rows(
        clova_client,
        sess_id=int(sess_id),
        messages=[
            {
                "msg_id": int(m["msg_id"]),
                "speaker": str(m.get("speaker", "")),
                "text": str(m.get("text", "")),
            }
            for m in msg_rows
        ],
        store_low=False,           # ✅ LOW 저장 안 함 → 호출 횟수 감소
        llm_only_if_rule_hit=False, # ✅ 모든 메시지 LLM 판단 → 정확도 향상
        use_llm=True,
    )

    f2 = analyze_feature2(clova_client, dialog_text)
    emotion_result = analyze_feature3(clova_client, msg_rows, batch_size=5)
    q4 = analyze_feature4(clova_client, dialog_text)

    # ── 3) DB 저장 ───────────────────────────
    
    # ✅ [신규 추가] 이 세션의 내담자가 선택한 고민 유형 중 우선순위(prio)가 가장 높은 것을 가져옵니다.
    # 의 client_topic 테이블 참조
    user_topic_id = db.execute(text("""
        SELECT ct.topic_id 
        FROM client_topic ct
        JOIN sess s ON ct.client_id = s.client_id
        WHERE s.id = :sid
        ORDER BY ct.prio ASC LIMIT 1
    """), {"sid": sess_id}).scalar()
    
    # 만약 선택한 토픽이 없다면 기존처럼 1(기타)을 기본값으로 사용합니다.
    actual_topic_id = int(user_topic_id) if user_topic_id else 1

    insert_alert_rows(db, f1_alert_rows)

    # ✅ [수정] topic_id=1 고정값을 actual_topic_id 변수로 교체합니다.
    upsert_sess_analysis(
        db,
        sess_id=sess_id,
        topic_id=actual_topic_id,
        summary=str(f2.get("summary", "")),
        note="",
    ) #

    insert_text_emotions(db, emotion_result.get("items", []))

    upsert_quality(db, sess_id=sess_id, flow=q4.get("flow", 50.0), score=q4.get("score", 50.0))

    logger.info(f"[runner] sess_id={sess_id} 분석 및 저장 완료")

    return {
        "feature1_alert_rows": f1_alert_rows,
        "feature2": f2,
        "emotion": emotion_result,
        "quality": q4,
    }