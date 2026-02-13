import streamlit as st
import pandas as pd
from common_ui import api_health_check_or_stop, api_get, pick_session_id

st.set_page_config(page_title="Session Detail UI", layout="wide")
st.title("📌 세션 상세 화면")

api_health_check_or_stop()

sess_id = pick_session_id(default_id=1)

# 세션 기본 정보
sess_r = api_get(f"/sessions/{sess_id}")
if not sess_r.ok:
    st.error(sess_r.text)
    st.stop()

st.subheader("세션 정보")
st.json(sess_r.json())

tab1, tab2, tab3, tab4 = st.tabs(["Messages", "Alerts", "Quality", "Analysis"])

with tab1:
    r = api_get(f"/sessions/{sess_id}/messages", params={"limit": 500})
    if r.ok:
        st.dataframe(pd.DataFrame(r.json().get("items", [])), use_container_width=True, height=520)
    else:
        st.error(r.text)

with tab2:
    r = api_get(f"/sessions/{sess_id}/alerts")
    if r.ok:
        items = r.json().get("items", [])
        if not items:
            st.info("알럿 없음")
        else:
            st.dataframe(pd.DataFrame(items), use_container_width=True, height=520)
    else:
        st.error(r.text)

with tab3:
    r = api_get(f"/sessions/{sess_id}/quality")
    if r.ok:
        st.json(r.json())
    else:
        st.error(r.text)

with tab4:
    r = api_get(f"/sessions/{sess_id}/analysis")
    if r.ok:
        st.dataframe(pd.DataFrame(r.json().get("items", [])), use_container_width=True, height=520)
    else:
        st.error(r.text)
