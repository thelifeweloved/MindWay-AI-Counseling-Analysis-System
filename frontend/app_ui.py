import streamlit as st
import requests

API = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="MindWay",
    page_icon="🧠",
    layout="wide"
)

# 화면 전체 중앙 정렬
st.markdown(
    """
    <style>
    .center-box {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 80vh;
        flex-direction: column;
        text-align: center;
    }
    .logo {
        font-size: 120px;
        margin-bottom: 10px;
    }
    .title {
        font-size: 56px;
        font-weight: 800;
        margin-bottom: 8px;
    }
    .subtitle {
        font-size: 18px;
        color: gray;
    }
    </style>

    <div class="center-box">
        <div class="logo">🧠</div>
        <div class="title">MindWay</div>
        <div class="subtitle">이탈 직전 신호 탐지 & 상담 품질 분석</div>
    </div>
    """,
    unsafe_allow_html=True
)

# 하단 상태 표시 (작게)
try:
    r = requests.get(f"{API}/health/db", timeout=2)
    if r.ok:
        st.caption("✅ API 연결 정상")
    else:
        st.caption("⚠️ API 응답 오류")
except:
    st.caption("❌ API 서버 연결 실패")
