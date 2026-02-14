import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime

# API 서버 주소 (main.py 실행 주소)
API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="사후 이탈 분석 상세", layout="wide")

# 스타일링 (이미지 205524.png의 디자인 스타일 반영)
st.markdown("""
    <style>
    .report-title { font-size: 28px; font-weight: 900; color: #1E1E1E; margin-bottom: 20px; }
    .metric-card { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="report-title">🔍 이탈 세션 상세 부검 리포트</p>', unsafe_allow_html=True)

# 1. 대상 상담사 선택 (실제 서비스에선 세션 정보 활용)
counselor_id = st.sidebar.number_input("상담사 ID", min_value=1, value=1)

# 2. 이탈 세션 목록 불러오기 (기능 1: 부검 리포트)
try:
    # main.py의 분석 엔드포인트 호출
    response = requests.get(f"{API_BASE}/sessions/dropout-reports", params={"counselor_id": counselor_id})
    if response.status_code == 200:
        reports = response.json().get("items", [])
        if not reports:
            st.warning("분석할 이탈 세션 데이터가 없습니다.")
            st.stop()
        
        df_reports = pd.DataFrame(reports)
        
        # 목록 출력 및 선택
        st.subheader("📋 최근 이탈 세션 목록")
        selected_sess = st.selectbox(
            "분석할 세션을 선택하세요",
            options=df_reports.to_dict('records'),
            format_func=lambda x: f"[{x['start_at']}] {x['client_name']} 내담자 ({x['duration_min']}분 상담)"
        )
        
        if selected_sess:
            st.divider()
            
            # 3. 상세 분석 레이아웃 (기능 2, 3, 4)
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("### ⏱️ 결정적 순간 타임라인")
                # 감정 궤적 데이터 호출
                timeline_res = requests.get(f"{API_BASE}/sessions/{selected_sess['sess_id']}/timeline")
                df_timeline = pd.DataFrame(timeline_res.json().get("items", []))
                
                if not df_timeline.empty:
                    # Plotly 차트: 감정 변화 추이
                    fig = px.line(df_timeline, x="at", y="emotion_score", color="speaker",
                                  title="세션 내 감정 변화 궤적", markers=True,
                                  color_discrete_map={"CLIENT": "#ff4b4b", "COUNSELOR": "#007bff"})
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 메시지 타임라인
                    st.write("**상세 대화 복기**")
                    st.dataframe(df_timeline[["at", "speaker", "text", "emotion", "alert_type"]], use_container_width=True)

            with col2:
                st.markdown("### 📊 세션 품질 지표")
                st.markdown(f"""
                <div class="metric-card">
                    <p><b>종합 품질 점수:</b> {selected_sess['quality_score']}점</p>
                    <p><b>대화 흐름 점수:</b> {selected_sess['flow_score']}점</p>
                    <p><b>탐지된 위험 신호:</b> {selected_sess['alert_count']}건</p>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("### 💬 위험 발언 패턴 분석")
                # 기능 3: 상담사 패턴 분석 호출
                patterns_res = requests.get(f"{API_BASE}/counselors/{counselor_id}/risk-patterns")
                patterns = patterns_res.json().get("items", [])
                if patterns:
                    st.table(pd.DataFrame(patterns))

except Exception as e:
    st.error(f"서버 연결 에러: {e}")