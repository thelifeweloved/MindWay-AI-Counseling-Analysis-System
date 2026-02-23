import streamlit as st
import pandas as pd
import plotly.express as px

from common_ui import api_health_check_or_stop, api_get

st.set_page_config(page_title="MindWay · Dashboard", page_icon="📊", layout="wide")

st.markdown("""
<style>
  html,body,[class*="css"]{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}
  .mw-h1{font-size:24px;font-weight:950;color:#111827;margin-bottom:2px;}
  .mw-sub{font-size:14px;color:#6b7280;font-weight:600;margin-bottom:18px;}
  .mw-card{border:1px solid #e5e7eb;border-radius:12px;padding:18px;background:#fff;
    box-shadow:0 1px 2px rgba(0,0,0,.05);margin-bottom:20px;}
  .mw-card-title{font-size:15px;font-weight:800;color:#111827;margin-bottom:12px;}
  .mw-alert-box{border-left:4px solid #ef4444;background:#fef2f2;
    padding:12px;margin:8px 0;border-radius:4px;}
  .mw-metric-label{font-size:13px;color:#6b7280;font-weight:700;}
  .mw-metric-value{font-size:26px;font-weight:900;color:#111827;}
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='mw-h1'>MindWay Dashboard</div>", unsafe_allow_html=True)
st.markdown("<div class='mw-sub'>상담 이탈 방지 및 품질 분석 운영 인터페이스</div>", unsafe_allow_html=True)

api_health_check_or_stop(show_success=False)

with st.sidebar:
    st.markdown("### 상담사 설정")
    counselor_id = st.number_input("접속 상담사 ID", min_value=1, value=1)
    data_limit   = st.slider("조회 범위", 20, 500, 100)
    st.divider()
    st.caption("테이블 명세서(2026.02.14) 기준 최적화")


def load_data(endpoint, params=None):
    """실패해도 빈 DataFrame 반환 — 대시보드 전체가 멈추지 않도록"""
    try:
        r = api_get(endpoint, params=params)
        if r is None or not r.ok:
            status = getattr(r, "status_code", "?")
            st.caption("⚠️ " + endpoint + " (" + str(status) + ")")
            return pd.DataFrame()
        items = r.json().get("items", [])
        return pd.DataFrame(items)
    except Exception as e:
        st.caption("⚠️ " + endpoint + " 오류: " + str(e))
        return pd.DataFrame()


df_sess   = load_data("/sessions",            {"limit": data_limit})
df_appt   = load_data("/appointments",        {"counselor_id": counselor_id})
df_missed = load_data("/stats/missed-alerts", {"counselor_id": counselor_id})

if not df_sess.empty:
    df_sess["start_at"] = pd.to_datetime(df_sess["start_at"], errors="coerce")
    df_my       = df_sess[df_sess["counselor_id"] == counselor_id].copy()
    total_cnt   = len(df_my)
    dropout_cnt = int((df_my.get("end_reason", pd.Series()) == "DROPOUT").sum())
    active_cnt  = int((df_my.get("progress",   pd.Series()) == "ACTIVE").sum())
    sat_rate    = float((df_my["sat"] == 1).mean() * 100) if "sat" in df_my.columns else 0.0
else:
    total_cnt = dropout_cnt = active_cnt = 0
    sat_rate  = 0.0

tab1, tab2, tab3 = st.tabs(["📊 운영 요약", "🚨 이탈 신호 관리", "📈 분석 리포트"])

# ── TAB 1 ────────────────────────────────────────────────
with tab1:
    m1, m2, m3, m4 = st.columns(4)
    for col, label, val, color in [
        (m1, "총 상담 세션",       str(total_cnt),              "#111827"),
        (m2, "현재 진행 중",       str(active_cnt),             "#111827"),
        (m3, "누적 이탈(DROPOUT)", str(dropout_cnt),            "#ef4444"),
        (m4, "평균 만족도",        str(round(sat_rate, 1)) + "%","#111827"),
    ]:
        col.markdown(
            "<div class='mw-card'>"
            "<div class='mw-metric-label'>" + label + "</div>"
            "<div class='mw-metric-value' style='color:" + color + ";'>" + val + "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.divider()
    col_left, col_right = st.columns([1.6, 1])

    with col_left:
        st.markdown("<div class='mw-card-title'>📅 예약 리스트 (appt)</div>", unsafe_allow_html=True)
        if df_appt.empty:
            st.info("예정된 예약이 없거나 데이터를 불러오지 못했습니다.")
        else:
            show_cols = [c for c in ["id","client_name","at","status","client_grade"] if c in df_appt.columns]
            st.dataframe(df_appt[show_cols], use_container_width=True, height=300)

        st.markdown("<div class='mw-card-title'>⚠️ 실시간 운영 경고</div>", unsafe_allow_html=True)
        if not df_missed.empty:
            st.markdown(
                "<div class='mw-alert-box'><b>알림 없이 이탈한 세션 "
                + str(len(df_missed)) + "건</b> — 룰 점검이 필요합니다.</div>",
                unsafe_allow_html=True,
            )
        else:
            st.success("특이사항 없음: 이탈 신호가 정상 탐지되고 있습니다.")

    with col_right:
        st.markdown("<div class='mw-card-title'>📡 채널별 분포</div>", unsafe_allow_html=True)
        if not df_sess.empty and "channel" in df_sess.columns:
            fig_ch = px.pie(df_sess, names="channel", hole=0.5,
                            color_discrete_sequence=["#6366f1","#10b981"])
            fig_ch.update_layout(margin=dict(t=0,b=0,l=0,r=0), height=220)
            st.plotly_chart(fig_ch, use_container_width=True)
        else:
            st.caption("채널 데이터 없음")

        st.markdown(
            "<div class='mw-card'><div class='mw-card-title'>💡 오늘의 조치 가이드</div>"
            "<ul>"
            "<li>등급이 <b>개선필요</b>인 내담자는 이전 리포트를 먼저 확인하세요.</li>"
            "<li>상담 중 <b>그만, 힘들</b> 반복 시 HCX 헬퍼를 호출하세요.</li>"
            "</ul></div>",
            unsafe_allow_html=True,
        )

# ── TAB 2 ────────────────────────────────────────────────
with tab2:
    st.subheader("🚨 위험 신호 탐지 내역 (alert)")
    if df_missed.empty:
        st.info("탐지 내역이 없거나 /stats/missed-alerts 엔드포인트가 main.py에 없습니다.")
        st.caption("main.py 에 아래 API를 추가하면 활성화됩니다.")
        st.markdown("""
```python
@app.get("/stats/missed-alerts")
def stats_missed_alerts(counselor_id: int = Query(..., ge=1), db: Session = Depends(get_db)):
    sql = \'\'\'
        SELECT a.* FROM alert a
        JOIN sess s ON a.sess_id = s.id
        WHERE s.counselor_id = :cid AND s.end_reason = \'DROPOUT\'
        ORDER BY a.at DESC LIMIT 100
    \'\'\'
    return {"items": jsonable_encoder(
        list(db.execute(text(sql), {"cid": counselor_id}).mappings().all())
    )}
```
""")
    else:
        st.dataframe(df_missed, use_container_width=True)

# ── TAB 3 ────────────────────────────────────────────────
with tab3:
    st.subheader("📈 사후 분석 리포트")

    a1, a2 = st.columns(2)
    with a1:
        st.markdown("#### 🧠 주제별 이탈 분석")
        df_topic = load_data("/stats/topic-dropout", {"counselor_id": counselor_id})
        if not df_topic.empty:
            fig = px.bar(df_topic, x=df_topic.columns[0], y=df_topic.columns[-1],
                         color=df_topic.columns[-1], color_continuous_scale="Reds")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("데이터 없음")

    with a2:
        st.markdown("#### 📡 채널별 이탈률")
        df_ch = load_data("/stats/channel-dropout", {"counselor_id": counselor_id})
        if not df_ch.empty:
            fig = px.bar(df_ch, x=df_ch.columns[0], y=df_ch.columns[-1],
                         text_auto=".1f", color_discrete_sequence=["#10b981"])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("데이터 없음")

    st.divider()
    b1, b2 = st.columns(2)
    with b1:
        st.markdown("#### ⏰ 시간대별 이탈률")
        df_time = load_data("/stats/time-dropout", {"counselor_id": counselor_id})
        if not df_time.empty:
            fig = px.line(df_time, x=df_time.columns[0], y=df_time.columns[-1],
                          markers=True, line_shape="spline")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("데이터 없음")

    with b2:
        st.markdown("#### 👥 내담자 등급 분포")
        df_grade = load_data("/stats/client-grade-dropout", {"counselor_id": counselor_id})
        if not df_grade.empty:
            fig = px.pie(df_grade, names=df_grade.columns[0], values=df_grade.columns[-1],
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("데이터 없음")

    st.divider()
    st.markdown("#### 📈 월별 성장 추이")
    df_growth = load_data("/stats/monthly-growth", {"counselor_id": counselor_id})
    if not df_growth.empty:
        fig = px.line(df_growth, x=df_growth.columns[0], y=df_growth.columns[-1],
                      markers=True, text=df_growth.columns[-1])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("데이터 없음")

st.divider()
st.caption("MindWay Agent System | Data Source: counseling_db | spec_v: 2026.02.14")