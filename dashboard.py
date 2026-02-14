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
    health = requests.get(f"{API}/health/db", timeout=3)
    st.success(f"API 연결 OK: {health.json()}")
except Exception as e:
    st.error(f"API 연결 실패: {e}")
    st.stop()

cid = st.number_input("상담사 ID", min_value=1, value=1)

# -------------------------
# 오늘 예약 리스트
# -------------------------
st.subheader("📅 오늘 예약 상담")

appt_resp = requests.get(f"{API}/appointments/today")

if appt_resp.status_code == 200:
    appts = appt_resp.json().get("items", [])
    if len(appts) == 0:
        st.info("오늘 예약 없음")
    else:
        st.dataframe(pd.DataFrame(appts), use_container_width=True)
else:
    st.warning("예약 API 없음")

st.divider()

# -------------------------
# 세션 목록
# -------------------------
st.subheader("📋 세션 목록")

sess_res = requests.get(f"{API}/sessions?limit=50").json()
sessions = sess_res.get("items", [])
count = sess_res.get("count", 0)

if count == 0:
    st.warning("세션 데이터 없음")
    st.stop()

df = pd.DataFrame(sessions)
st.dataframe(df, use_container_width=True)

sess_id = st.selectbox("세션 선택", df["id"].tolist())

# -------------------------
# 세션 대시보드
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
# 상담 시뮬레이터
# -------------------------
st.subheader("💬 상담 시뮬레이터")

speaker = st.radio("발화자", ["CLIENT", "COUNSELOR", "SYSTEM"], horizontal=True)

speaker_id = st.number_input("speaker_id", min_value=1, value=1)

if speaker == "SYSTEM":
    speaker_id = None

text = st.text_area("메시지 입력")

if st.button("전송"):
    payload = {
        "sess_id": int(sess_id),
        "speaker": speaker,
        "speaker_id": speaker_id,
        "text": text,
        "stt_conf": 0.95
    }

    resp = requests.post(f"{API}/messages", json=payload)

    if resp.ok:
        st.success(resp.json())
        st.rerun()
    else:
        st.error(resp.text)

st.divider()

# -------------------------
# 대화 / 알림
# -------------------------
col3, col4 = st.columns(2)

with col3:
    st.markdown("### 대화 내용")
    msgs = requests.get(f"{API}/sessions/{sess_id}/messages?limit=200").json().get("items", [])
    if len(msgs) == 0:
        st.info("대화 없음")
    else:
        st.dataframe(pd.DataFrame(msgs), use_container_width=True)

with col4:
    st.markdown("### 이탈 신호")
    alerts = requests.get(f"{API}/sessions/{sess_id}/alerts").json().get("items", [])
    if len(alerts) == 0:
        st.info("알림 없음")
    else:
        st.dataframe(pd.DataFrame(alerts), use_container_width=True)

st.divider()

# -------------------------
# 분석 기능 영역
# -------------------------
st.header("📊 사후 분석 기능")

def show(title, url):
    st.markdown(f"### {title}")
    r = requests.get(url)
    if r.status_code == 200:
        items = r.json().get("items", [])
        if len(items) == 0:
            st.info("데이터 없음")
        else:
            st.dataframe(pd.DataFrame(items), use_container_width=True)
    else:
        st.error("API 오류")

show("주제별 이탈률", f"{API}/stats/topic-dropout?counselor_id={cid}")
show("내담자 등급별 이탈", f"{API}/stats/client-grade-dropout?counselor_id={cid}")
show("알림 없이 이탈", f"{API}/stats/missed-alerts?counselor_id={cid}")
show("시간대별 이탈", f"{API}/stats/time-dropout?counselor_id={cid}")
show("채널별 비교", f"{API}/stats/channel-dropout?counselor_id={cid}")
show("월별 성장 추이", f"{API}/stats/monthly-growth?counselor_id={cid}")
