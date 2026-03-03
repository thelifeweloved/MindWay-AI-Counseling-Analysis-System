import streamlit as st
import requests
# [수정] common_ui에서 정의한 헬퍼 함수들을 가져오게
from common_ui import get_api_base, api_health_check_or_stop

# 테이블 명세서 기반 MindWay 프로젝트 메인 랜딩 설정
st.set_page_config(
    page_title="MindWay",
    page_icon=None,  
    layout="wide"
)

# -------------------------
# 🎨 Styles (MindWay Brand Identity)
# -------------------------
st.markdown("""
<style>
html, body, [class*="css"]  {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.center-wrap {
    height: 80vh;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    text-align: center;
}

.title {
    font-size: 72px;
    font-weight: 900;
    letter-spacing: -2px;
    color: #111827;
    margin-bottom: 8px;
}

.subtitle {
    font-size: 22px;
    color: #4b5563;
    font-weight: 500;
    margin-bottom: 48px;
    line-height: 1.6;
}

.badge {
    font-size: 14px;
    padding: 8px 18px;
    border-radius: 999px;
    background: #f3f4f6;
    color: #374151;
    font-weight: 700;
    margin-bottom: 24px;
    border: 1px solid #e5e7eb;
}

.footer {
    position: fixed;
    bottom: 20px;
    left: 0;
    right: 0;
    text-align: center;
    font-size: 13px;
    color: #9ca3af;
    font-weight: 500;
}

/* 버튼이나 링크가 필요한 경우를 대비한 힌트 */
.hint {
    font-size: 14px;
    color: #6366f1;
    font-weight: 600;
    text-decoration: none;
}
</style>

<div class="center-wrap">
    <div class="badge">MindWay Counseling Intelligence System</div>
    <div class="title">MindWay</div>
    <div class="subtitle">
        상담 이탈 직전 신호 탐지 및 품질 분석을 위한<br>
        데이터 기반 의사결정 보조 인터페이스
    </div>
    <div class="hint">← 왼쪽 사이드바에서 메뉴를 선택하여 시작하세요</div>
</div>
""", unsafe_allow_html=True)

# -------------------------
# 📡 API/DB Health Check (수정 포인트)
# -------------------------
# [수정] 하드코딩된 127.0.0.1 대신 common_ui의 get_api_base()를 활용합니다.
try:
    # 헬스체크를 수행하고 결과를 가져옵니다.
    health_data = api_health_check_or_stop(show_success=False)
    
    # 멘토님 요청 반영: 시스템 접속 정보를 푸터에 명시하여 기술적 구체성 확보
    api_host = get_api_base()
    db_status = "Connected" if health_data.get("db") == "ok" else "Error"
    
    st.markdown(
        f'<div class="footer">● API Host: {api_host} | ● Database: mindway (Port 3307) {db_status}</div>', 
        unsafe_allow_html=True
    )
except Exception:
    st.markdown('<div class="footer" style="color:#ef4444;">● API Server Disconnected (Check .env or Server Status)</div>', unsafe_allow_html=True)