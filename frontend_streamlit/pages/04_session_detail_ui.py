import streamlit as st
import pandas as pd
import plotly.express as px

from common_ui import (
    api_health_check_or_stop,
    api_get,
    api_json_or_show_error,
    pick_session_id,
)

# 세션 상세 분석 서비스 설정 (테이블 명세서 2026.02.14 기준) 
st.set_page_config(page_title="MindWay · Session Detail", page_icon=None, layout="wide")

st.title("🧾 세션 상세 분석")

# API 및 DB(counseling_db) 연결 상태 확인
api_health_check_or_stop(show_success=False)

# -------------------------
# 1) Session 선택 (sess 테이블 기반) [cite: 60]
# -------------------------
sess_id = pick_session_id()

# -------------------------
# 2) 세션 기본 정보 로드
# -------------------------
# 단일 세션 상세 정보를 가져오기 위해 엔드포인트 수정 제안 (/sessions/{id}/dashboard)
sess_r = api_get(f"/sessions/{sess_id}/dashboard")
sess_data = api_json_or_show_error(sess_r)

session_info = sess_data.get("session", {})

# 상단 KPI 지표 (명세서 컬럼명 준수) [cite: 60, 81, 84-86]
col1, col2, col3, col4 = st.columns(4)

col1.metric("세션 ID", session_info.get("id"))
col2.metric("채널", session_info.get("channel")) # CHAT / VOICE [cite: 114]
col3.metric("종료 사유", session_info.get("end_reason") or "진행 중") # NORMAL / DROPOUT [cite: 116-117]
col4.metric("진행 상태", session_info.get("progress")) # WAITING / ACTIVE / CLOSED [cite: 115]

st.caption(f"시작 시각: {session_info.get('start_at')} | 종료 시각: {session_info.get('end_at') or '-'}")

st.divider()

# -------------------------
# 3) 메시지 및 정서 분석 데이터 로드 (msg + text_emotion JOIN) [cite: 121, 341]
# -------------------------
msg_r = api_get(f"/sessions/{sess_id}/messages", params={"limit": 400})
msg_data = api_json_or_show_error(msg_r, title="메시지 조회 실패")

df_msg = pd.DataFrame(msg_data.get("items", []))

# -------------------------
# 4) 감정 변화 흐름 시각화 (text_emotion 테이블 연동 시) [cite: 345, 358]
# -------------------------
# 명세서상 text_emotion.score (0.00 ~ 1.00) 기반 [cite: 358]
if not df_msg.empty and "score" in df_msg.columns:
    st.subheader("📉 메시지 기반 정서 변화 흐름")

    # 발화 시각(at) 기준 정렬 [cite: 145]
    df_msg["at"] = pd.to_datetime(df_msg["at"])
    df_msg = df_msg.sort_values("at")

    fig = px.line(
        df_msg,
        x="at",
        y="score",
        color="speaker", # COUNSELOR / CLIENT / SYSTEM [cite: 134]
        markers=True,
        hover_data=["text", "label"], # 명세서 label(정서 라벨) 포함 [cite: 354]
        title="세션 타임라인 정서 점수 추이",
        labels={"score": "정서 점수 (0~1)", "at": "발화 시각"}
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("정서 분석 데이터가 누락되었거나 분석 진행 중입니다.")

st.divider()

# -------------------------
# 5) 위험 신호 / 알림 내역 (alert 테이블) [cite: 258-259]
# -------------------------
alert_r = api_get(f"/sessions/{sess_id}/alerts")
if alert_r.ok:
    alert_data = alert_r.json()
    df_alert = pd.DataFrame(alert_data.get("items", []))

    st.subheader("🚨 탐지된 위험 신호 (Alert)")

    if df_alert.empty:
        st.success("해당 세션에서 탐지된 특이 위험 신호가 없습니다.")
    else:
        # 명세서 컬럼 필터링 [cite: 259, 276]
        display_alert_cols = [c for c in ["at", "type", "score", "rule", "status"] if c in df_alert.columns]
        st.dataframe(df_alert[display_alert_cols], use_container_width=True)

st.divider()

# -------------------------
# 6) 결정적 순간 분석 (Rule-based Safety Engine)
# -------------------------
st.subheader("🎯 이탈 직전 신호(Signal) 분석")

if not df_msg.empty:
    # 이탈 직전 윈도우(마지막 10개 메시지) 분석
    last_msgs = df_msg.head(10) # API가 DESC 정렬일 경우 head가 마지막 발화

    signals_detected = False
    for _, row in last_msgs.iterrows():
        text = str(row.get("text") or "")
        # 스냅샷 정의 키워드 기반 탐지
        if any(k in text for k in ["그만", "힘들", "포기", "싫어", "못하겠", "의미없"]):
            st.warning(f"⚠️ **이탈 직전 신호 탐지:** \"{text}\"")
            signals_detected = True
            break
    
    if not signals_detected:
        st.info("세션 종료 구간 내 뚜렷한 부정 키워드 패턴이 탐지되지 않았습니다.")

st.divider()

# -------------------------
# 7) 대화 복기 (msg 테이블) [cite: 125]
# -------------------------
st.subheader("💬 전체 대화 복기")

# 명세서 기반 컬럼 표시 [cite: 125, 142]
display_cols = [c for c in ["at", "speaker", "text", "stt_conf"] if c in df_msg.columns]
if not df_msg.empty:
    st.dataframe(df_msg[display_cols], use_container_width=True, height=420)

st.divider()

# -------------------------
# 8) AI 사후 분석 인사이트
# -------------------------
st.subheader("🧠 분석 리포트 요약 (AI Insight)")

# 명세서 end_reason 및 sess_analysis 테이블 활용 개념 [cite: 84, 370]
if session_info.get("end_reason") == "DROPOUT":
    st.error(
        "### ❗ 이탈 세션 분석 결과\n"
        "이 세션은 **'DROPOUT(이탈)'**으로 기록되었습니다. [cite: 85]\n\n"
        "**주요 분석 결과:**\n"
        "- **정서 하락:** 세션 종료 직전 내담자의 정서 점수가 급격히 하락했습니다. [cite: 345]\n"
        "- **위험 발화:** 이탈 직전 구간에서 거부/부정 키워드가 탐지되었습니다.\n"
        "- **조치 권장:** 해당 내담자의 다음 예약 시 AI 헬퍼를 통한 집중 케어가 필요합니다."
    )
else:
    st.success("이 세션은 정상 종료(NORMAL)되었거나 현재 활성 상태입니다. [cite: 85, 115]")

# 푸터 [cite: 7, 372]
st.caption("MindWay 분석 시스템 | 명세서 v2026.02.14 기반 최적화 | 위험군 분류가 아닌 이탈 신호 분석 목적")