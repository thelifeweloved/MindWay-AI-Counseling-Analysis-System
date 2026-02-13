import streamlit as st
import requests
import pandas as pd

API = "http://127.0.0.1:8000"

st.set_page_config(page_title="Mindway Dashboard", layout="wide")
st.title("🧠 Mindway 상담 대시보드")

# -------------------------
# Health check
# -------------------------
try:
    r = requests.get(f"{API}/health/db", timeout=3)
    st.success(f"API 연결 OK: {r.json()}")
except Exception as e:
    st.error(f"API 연결 실패: {e}")
    st.stop()

# -------------------------
# Sessions
# -------------------------
st.subheader("📋 세션 목록")
sess_res = requests.get(f"{API}/sessions?limit=50").json()
sessions = sess_res.get("items", [])
count = sess_res.get("count", 0)

if count == 0:
    st.warning("현재 등록된 상담 세션이 없습니다. seed_min.sql 또는 seed.sql을 실행해주세요.")
    st.stop()

df = pd.DataFrame(sessions)
st.dataframe(df, use_container_width=True)

sess_id = st.selectbox("세션 선택", df["id"].tolist())


# -------------------------
# Dashboard data
# -------------------------
st.subheader("📌 세션 대시보드")
dash = requests.get(f"{API}/sessions/{sess_id}/dashboard").json()

col1, col2 = st.columns(2)
with col1:
    st.markdown("### 세션 정보")
    st.json(dash.get("session", {}))

with col2:
    st.markdown("### Risk Score")
    st.metric("이탈 위험도", dash.get("risk_score", 0.0))

st.divider()

# -------------------------
# 실시간 시뮬레이터 (메시지 전송)
# -------------------------
st.subheader("💬 상담 시뮬레이터 (실시간 탐지)")

speaker = st.radio("발화자", ["CLIENT", "COUNSELOR", "SYSTEM"], horizontal=True)

speaker_id = st.number_input("speaker_id (SYSTEM이면 비워도 됨)", min_value=0, value=1, step=1)
if speaker == "SYSTEM":
    speaker_id = None

text = st.text_area("메시지 입력", placeholder="예) 상담 너무 힘들어요 그만하고 싶어요")

if st.button("전송"):
    payload = {
        "sess_id": int(sess_id),
        "speaker": speaker,
        "speaker_id": speaker_id,
        "text": text
    }
    resp = requests.post(f"{API}/messages", json=payload)

    if resp.ok:
        st.success(resp.json())
        st.rerun()
    else:
        st.error(f"API 오류 {resp.status_code}")
        st.code(resp.text)

st.divider()

# -------------------------
# Messages + Alerts
# -------------------------
col3, col4 = st.columns(2)

with col3:
    st.markdown("### 대화 내용 (최근 200)")
    msgs = requests.get(f"{API}/sessions/{sess_id}/messages?limit=200").json().get("items", [])
    st.dataframe(pd.DataFrame(msgs), use_container_width=True)

with col4:
    st.markdown("### 이탈 신호 (alerts)")
    alerts = requests.get(f"{API}/sessions/{sess_id}/alerts").json().get("items", [])
    if len(alerts) == 0:
        st.info("알럿 없음")
    else:
        st.dataframe(pd.DataFrame(alerts), use_container_width=True)