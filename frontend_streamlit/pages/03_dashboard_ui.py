import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date

from common_ui import (
    api_health_check_or_stop,
    api_get,
    api_json_or_show_error,
)

st.set_page_config(page_title="MindWay · Dashboard", page_icon="📊", layout="wide")

# -------------------------
# Styles (Refined Professional Identity)
# -------------------------
st.markdown(
    """
    <style>
      html, body, [class*="css"]{font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;}
      .mw-h1{font-size:24px;font-weight:950;color:#111827;margin-bottom:2px;}
      .mw-sub{font-size:14px;color:#6b7280;font-weight:600;margin-bottom:18px;}
      .mw-card{
        border:1px solid #e5e7eb; border-radius:12px; padding:18px; background:#ffffff;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05); margin-bottom: 20px;
      }
      .mw-card-title{font-size:15px;font-weight:800;color:#111827;margin-bottom:12px;display:flex;align-items:center;gap:6px;}
      .mw-badge{display:inline-block;padding:4px 10px;border-radius:999px;background:#f3f4f6;color:#374151;font-weight:750;font-size:12px;}
      .mw-alert-box{border-left: 4px solid #ef4444; background:#fef2f2; padding:12px; margin: 8px 0; border-radius:4px;}
      .mw-metric-label{font-size:13px; color:#6b7280; font-weight:700;}
      .mw-metric-value{font-size:26px; font-weight:900; color:#111827;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="mw-h1">MindWay Dashboard</div>', unsafe_allow_html=True)
st.markdown('<div class="mw-sub">상담 이탈 방지 및 품질 분석 운영 인터페이스</div>', unsafe_allow_html=True)

api_health_check_or_stop(show_success=False)

# -------------------------
# Sidebar
# -------------------------
with st.sidebar:
    st.markdown("### 👤 상담사 설정")
    counselor_id = st.number_input("접속 상담사 ID", min_value=1, value=1)
    data_limit = st.slider("조회 범위", 20, 500, 100)
    st.divider()
    st.caption("테이블 명세서(2026.02.14) 기준 최적화")

# -------------------------
# Data Loaders (Based on Table Spec)
# -------------------------
def load_data(endpoint, params=None):
    r = api_get(endpoint, params=params)
    data = api_json_or_show_error(r, title=f"{endpoint} 로드 실패")
    return pd.DataFrame(data.get("items", []))

# DB 로드
df_sess = load_data("/sessions", {"limit": data_limit})
df_appt = load_data("/appointments", {"counselor_id": counselor_id}) 
df_missed = load_data("/stats/missed-alerts", {"counselor_id": counselor_id})

# -------------------------
# Logic & KPI Calculation
# -------------------------
today = date.today()

if not df_sess.empty:
    df_sess["start_at"] = pd.to_datetime(df_sess["start_at"], errors="coerce")
    df_my_sess = df_sess[df_sess["counselor_id"] == counselor_id].copy()
    
    total_cnt = len(df_my_sess)
    dropout_cnt = len(df_my_sess[df_my_sess["end_reason"] == "DROPOUT"]) # 명세서 기준 [cite: 60, 84-86]
    active_cnt = len(df_my_sess[df_my_sess["progress"] == "ACTIVE"]) # 명세서 기준 [cite: 60, 81]
    sat_rate = (df_my_sess["sat"] == 1).mean() * 100 if "sat" in df_my_sess.columns else 0 # 만족도 1/0 기준 [cite: 60, 88]
else:
    total_cnt = dropout_cnt = active_cnt = sat_rate = 0

# -------------------------
# Main Tabs
# -------------------------
tab1, tab2, tab3 = st.tabs(["📊 운영 요약", "🚨 이탈 신호 관리", "📈 분석 리포트"])

# =========================================================
# TAB 1: 운영 요약
# =========================================================
with tab1:
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.markdown(f"<div class='mw-card'><div class='mw-metric-label'>총 상담 세션</div><div class='mw-metric-value'>{total_cnt}</div></div>", unsafe_allow_html=True)
    with m2: st.markdown(f"<div class='mw-card'><div class='mw-metric-label'>현재 진행 중</div><div class='mw-metric-value'>{active_cnt}</div></div>", unsafe_allow_html=True)
    with m3: st.markdown(f"<div class='mw-card'><div class='mw-metric-label'>누적 이탈(DROPOUT)</div><div class='mw-metric-value' style='color:#ef4444;'>{dropout_cnt}</div></div>", unsafe_allow_html=True)
    with m4: st.markdown(f"<div class='mw-card'><div class='mw-metric-label'>평균 만족도</div><div class='mw-metric-value'>{sat_rate:.1f}%</div></div>", unsafe_allow_html=True)

    st.divider()

    col_left, col_right = st.columns([1.6, 1])

    with col_left:
        st.markdown("<div class='mw-card-title'>📅 오늘의 예약 리스트 (appt)</div>", unsafe_allow_html=True)
        if df_appt.empty:
            st.info("오늘 예정된 예약이 없습니다.")
        else:
            show_appt = df_appt[["id", "client_name", "at", "status", "client_grade"]].copy() 
            st.dataframe(show_appt, use_container_width=True, height=350)

        st.markdown("<div class='mw-card-title'>⚠️ 실시간 운영 경고</div>", unsafe_allow_html=True)
        if not df_missed.empty:
            st.markdown(f"<div class='mw-alert-box'><b>알림 없이 이탈한 세션이 {len(df_missed)}건 있습니다.</b> 룰 점검이 필요합니다.</div>", unsafe_allow_html=True)
        else:
            st.success("특이사항 없음: 모든 이탈 신호가 정상 탐지되고 있습니다.")

    with col_right:
        st.markdown("<div class='mw-card-title'>📡 채널별 분포 (CHAT vs VOICE)</div>", unsafe_allow_html=True)
        if not df_sess.empty and "channel" in df_sess.columns:
            fig_ch = px.pie(df_sess, names="channel", hole=0.5, 
                            color_discrete_sequence=["#6366f1", "#10b981"])
            fig_ch.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=250)
            st.plotly_chart(fig_ch, use_container_width=True)
        
        st.markdown("<div class='mw-card'><div class='mw-card-title'>💡 오늘의 조치 가이드</div>", unsafe_allow_html=True)
        st.markdown("""
        - **예약 확인**: 배정된 내담자의 등급(`status`)이 **'개선필요'**라면 이전 분석 리포트를 먼저 확인하세요.
        - **이탈 징후**: 상담 중 **'그만', '힘들'** 키워드가 반복되면 HCX 도움말을 호출하세요.
        """)
        st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# TAB 2: 이탈 신호 관리
# =========================================================
with tab2:
    st.subheader("🚨 위험 신호 탐지 내역 (alert)")
    st.dataframe(df_missed, use_container_width=True)

# =========================================================
# TAB 3: 분석 리포트 (추가 그래프 보강)
# =========================================================
with tab3:
    st.subheader("📈 사후 분석 리포트 (품질 향상 지표)")
    
    # 1. 주제별 및 채널별 이탈률 분석
    a1, a2 = st.columns(2)
    with a1:
        st.markdown("#### 🧠 주제별 이탈 분석 (topic)")
        df_topic = load_data("/stats/topic-dropout", {"counselor_id": counselor_id})
        if not df_topic.empty:
            # 첫 번째 컬럼(주제명), 마지막 컬럼(이탈률) 기준 시각화
            fig_topic = px.bar(df_topic, x=df_topic.columns[0], y=df_topic.columns[-1], 
                               color=df_topic.columns[-1], color_continuous_scale="Reds")
            st.plotly_chart(fig_topic, use_container_width=True)
            
    with a2:
        st.markdown("#### 📡 채널별 이탈률 (channel)")
        # sess 테이블의 channel 컬럼 기반 이탈률 분석 API 가정 [cite: 7, 60]
        df_ch_dropout = load_data("/stats/channel-dropout", {"counselor_id": counselor_id})
        if not df_ch_dropout.empty:
            fig_ch_dr = px.bar(df_ch_dropout, x=df_ch_dropout.columns[0], y=df_ch_dropout.columns[-1],
                               text_auto='.1f', color_discrete_sequence=["#10b981"])
            st.plotly_chart(fig_ch_dr, use_container_width=True)

    st.divider()

    # 2. 리스크 스코어 추이 및 내담자 등급별 만족도
    b1, b2 = st.columns(2)
    with b1:
        st.markdown("#### ⏰ 시간 경과별 리스크 스코어 추이 (alert)")
        # alert 테이블의 score 값을 시간 순서대로 정렬한 데이터 [cite: 259]
        df_risk_trend = load_data("/stats/time-dropout", {"counselor_id": counselor_id}) 
        if not df_risk_trend.empty:
            fig_risk = px.line(df_risk_trend, x=df_risk_trend.columns[0], y=df_risk_trend.columns[-1],
                               markers=True, line_shape="spline")
            st.plotly_chart(fig_risk, use_container_width=True)
            st.caption("상담 진행 시간대별 평균 이탈률 변화를 나타냅니다.")

    with b2:
        st.markdown("#### 👥 내담자 등급별 만족도 (client)")
        # client.status 등급별 sess.sat 만족도 평균 분석 [cite: 14, 60]
        df_grade_sat = load_data("/stats/client-grade-dropout", {"counselor_id": counselor_id})
        if not df_grade_sat.empty:
            # 등급별 분포 혹은 만족도 수치 시각화
            fig_grade = px.pie(df_grade_sat, names=df_grade_sat.columns[0], values=df_grade_sat.columns[-1],
                               color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_grade, use_container_width=True)

    # 3. 월별 성장 및 품질 지표
    st.divider()
    st.markdown("#### 📈 월별 서비스 성장 및 품질 추이")
    df_growth = load_data("/stats/monthly-growth", {"counselor_id": counselor_id})
    if not df_growth.empty:
        fig_growth = px.line(df_growth, x=df_growth.columns[0], y=df_growth.columns[-1], 
                             markers=True, text=df_growth.columns[-1])
        st.plotly_chart(fig_growth, use_container_width=True)

# -------------------------
# Footer
# -------------------------
st.divider()
st.caption(f"MindWay Agent System | Data Source: counseling_db | spec_v: 2026.02.14")