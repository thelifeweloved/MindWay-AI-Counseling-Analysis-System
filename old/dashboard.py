import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# =========================
# Config
# =========================
API = "http://project-db-campus.smhrd.com:8000"

st.set_page_config(page_title="Mindway Dashboard", layout="wide")
st.title("🧠 Mindway 상담 대시보드")

# =========================
# Helpers
# =========================
def api_get(path: str, params=None, timeout=5):
    try:
        r = requests.get(f"{API}{path}", params=params, timeout=timeout)
        return r
    except Exception as e:
        st.error(f"API 호출 실패: {path} ({e})")
        return None

def api_post(path: str, json=None, timeout=8):
    try:
        r = requests.post(f"{API}{path}", json=json, timeout=timeout)
        return r
    except Exception as e:
        st.error(f"API 호출 실패: {path} ({e})")
        return None

def risk_badge(label: str, score: float):
    """
    main.py에서 risk_label(HIGH/MID/LOW) 내려오는 구조에 맞춘 표시
    """
    label = (label or "LOW").upper()
    if label == "HIGH":
        st.error(f"🚨 HIGH ({score:.2f})")
    elif label == "MID":
        st.warning(f"⚠️ MID ({score:.2f})")
    else:
        st.success(f"✅ LOW ({score:.2f})")

# =========================
# Health check
# =========================
health = api_get("/health/db", timeout=3)
if not health or health.status_code != 200:
    st.error(f"API 연결 실패: {None if not health else health.text}")
    st.stop()
st.success(f"API 연결 OK: {health.json()}")

# =========================
# Counselor scope
# =========================
cid = st.number_input("상담사 ID (counselor.id)", min_value=1, value=1)

st.divider()

# =========================
# Today appointments
# =========================
st.subheader("📅 오늘 예약 상담 (appt)")
appt_resp = api_get("/appointments", params={"counselor_id": cid}, timeout=5)

if appt_resp and appt_resp.status_code == 200:
    appts = appt_resp.json().get("items", [])
    if not appts:
        st.info("오늘 배정된 예약이 없습니다.")
    else:
        st.dataframe(pd.DataFrame(appts), use_container_width=True)
else:
    st.warning(f"예약 API를 불러올 수 없습니다 (Error: {None if not appt_resp else appt_resp.status_code})")

st.divider()

# =========================
# Sessions list (scoped)
# =========================
st.subheader("📋 세션 목록 (sess)")

# ✅ 핵심: counselor_id 스코프 필터 적용 (운영툴/문서 정합)
sess_resp = api_get("/sessions", params={"counselor_id": cid, "limit": 50}, timeout=6)
if not sess_resp or sess_resp.status_code != 200:
    st.error(f"세션 목록 API 호출 실패: {None if not sess_resp else sess_resp.text}")
    st.stop()

sess_json = sess_resp.json()
sessions = sess_json.get("items", [])
count = sess_json.get("count", 0)

if count == 0:
    st.warning("해당 상담사 ID에 대한 세션이 없습니다.")
    st.stop()

df_sess = pd.DataFrame(sessions)
st.dataframe(df_sess, use_container_width=True)

sess_id = st.selectbox("분석할 세션 선택 (sess.id)", df_sess["id"].tolist())

st.divider()

# =========================
# Session dashboard (summary-first)
# =========================
st.subheader("📌 세션 상세 대시보드")

dash_resp = api_get(f"/sessions/{sess_id}/dashboard", timeout=6)
if not dash_resp or dash_resp.status_code != 200:
    st.error(f"세션 대시보드 API 호출 실패: {None if not dash_resp else dash_resp.text}")
    st.stop()

dash = dash_resp.json()

# main.py 호환 키:
session = dash.get("session", {})   # 기존 유지
risk_score = float(dash.get("risk_score", 0.0) or 0.0)
risk_label = dash.get("risk_label", "LOW")  # 추가
quality = dash.get("quality")  # 추가 (없을 수 있음)
alert_summary = dash.get("alert_summary", {})  # 추가
alert_types = dash.get("alert_types", [])  # 추가

top1, top2, top3, top4 = st.columns(4)
with top1:
    st.markdown("### Risk")
    risk_badge(risk_label, risk_score)

with top2:
    st.markdown("### Alert Count")
    st.metric("전체 Alerts", int(alert_summary.get("total_alerts", 0) or 0))

with top3:
    st.markdown("### Detected")
    st.metric("DETECTED", int(alert_summary.get("detected_alerts", 0) or 0))

with top4:
    st.markdown("### Max Score")
    st.metric("최대 score", float(alert_summary.get("max_score", 0.0) or 0.0))

mid1, mid2 = st.columns([1, 1])
with mid1:
    st.markdown("### 세션 정보 (sess)")
    st.json(session)

with mid2:
    st.markdown("### 품질 요약 (quality)")
    if quality is None:
        st.info("quality 데이터가 없습니다. (세션 종료 후 사후 분석/적재 전 상태일 수 있음)")
    else:
        q_flow = quality.get("flow")
        q_score = quality.get("score")
        q_created = quality.get("created_at")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Flow", f"{float(q_flow):.2f}" if q_flow is not None else "N/A")
        with c2:
            st.metric("Score", f"{float(q_score):.2f}" if q_score is not None else "N/A")
        st.caption(f"created_at: {q_created}")

st.divider()

# =========================
# Session signal demo (msg + alert)
# =========================
st.subheader("💬 상담 기록 입력 & 신호 탐지 데모 (세션 로그 기반)")

speaker = st.radio("발화자 선택 (msg.speaker)", ["CLIENT", "COUNSELOR", "SYSTEM"], horizontal=True)

# SYSTEM이면 speaker_id는 NULL 허용(명세서) → 입력 UI 자체를 숨김
speaker_id = None
if speaker != "SYSTEM":
    speaker_id = st.number_input("발화자 고유 ID (speaker_id)", min_value=1, value=1)
else:
    st.caption("SYSTEM 발화는 speaker_id를 저장하지 않습니다. (NULL)")

text = st.text_area("메시지 입력 (msg.text)")

stt_conf = st.slider("STT 신뢰도 (msg.stt_conf)", min_value=0.0, max_value=1.0, value=0.95, step=0.01)

if st.button("메시지 저장"):
    payload = {
        "sess_id": int(sess_id),
        "speaker": speaker,
        "speaker_id": speaker_id,   # SYSTEM이면 None
        "text": text,
        "stt_conf": float(stt_conf),
    }
    resp = api_post("/messages", json=payload, timeout=8)

    if resp and resp.ok:
        st.success("저장 완료: msg 적재 + (CLIENT 발화 시) alert 탐지/적재")
        st.rerun()
    else:
        st.error(f"저장 실패: {None if not resp else resp.text}")

st.divider()

# =========================
# Logs (detail)
# =========================
col3, col4 = st.columns(2)

with col3:
    st.markdown("### 대화 기록 로그 (msg)")
    msgs_resp = api_get(f"/sessions/{sess_id}/messages", params={"limit": 200}, timeout=8)
    if msgs_resp and msgs_resp.status_code == 200:
        msgs = msgs_resp.json().get("items", [])
        if not msgs:
            st.info("기록된 대화가 없습니다.")
        else:
            st.dataframe(pd.DataFrame(msgs), use_container_width=True)
    else:
        st.error(f"msg 조회 실패: {None if not msgs_resp else msgs_resp.text}")

with col4:
    st.markdown("### 탐지된 이탈 신호 (alert)")
    alerts_resp = api_get(f"/sessions/{sess_id}/alerts", params={"limit": 200}, timeout=8)
    if alerts_resp and alerts_resp.status_code == 200:
        alerts = alerts_resp.json().get("items", [])
        if not alerts:
            st.info("탐지된 위험 신호가 없습니다.")
        else:
            st.dataframe(pd.DataFrame(alerts), use_container_width=True)
    else:
        st.error(f"alert 조회 실패: {None if not alerts_resp else alerts_resp.text}")

# alert_types(요약 분포)는 세션 대시보드 응답에 포함 → 추가로 시각화/표시
if alert_types:
    st.markdown("### Alert 타입 분포 (세션 요약)")
    st.dataframe(pd.DataFrame(alert_types), use_container_width=True)

st.divider()

# =========================
# Post-analysis reports (stats)
# =========================
st.header("📊 사후 분석 리포트 (통계)")

def show_analysis(title, path, params):
    st.markdown(f"#### {title}")
    r = api_get(path, params=params, timeout=10)
    if not r:
        st.error("통계 API 호출 실패(네트워크)")
        return
    if r.status_code != 200:
        st.error(f"통계 API 호출 실패 (상태 코드: {r.status_code})")
        return

    items = r.json().get("items", [])
    if not items:
        st.info("분석할 데이터가 부족합니다.")
        return
    st.dataframe(pd.DataFrame(items), use_container_width=True)

params = {"counselor_id": cid}

show_analysis("주제별 이탈률 (topic)", "/stats/topic-dropout", params)
show_analysis("내담자 등급별 이탈 분포 (client.status)", "/stats/client-grade-dropout", params)
show_analysis("탐지 실패 세션 (Missed Alerts)", "/stats/missed-alerts", params)
show_analysis("시간대별 이탈 패턴", "/stats/time-dropout", params)
show_analysis("채널별 이탈 비교 (CHAT vs VOICE)", "/stats/channel-dropout", params)
show_analysis("세션 품질/만족 추이 (quality & sat)", "/stats/quality-trend", params)

st.caption("MindWay Analytics System | Spec: 2026.02.14 (Table Spec aligned)")