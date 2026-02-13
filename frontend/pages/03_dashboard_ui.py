# frontend/pages/03_dashboard_ui.py
import streamlit as st
import pandas as pd
import plotly.express as px

from common_ui import api_health_check_or_stop, api_get

# --------------------------------
# Page config
# --------------------------------
st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
api_health_check_or_stop()

# --------------------------------
# Styles (실무형 + 숫자 크게 + 정렬 안정)
# --------------------------------
st.markdown(
    """
    <style>
      .stApp { background-color: #f6f7fb; }

      .mw-header{
        display:flex; align-items:center; justify-content:space-between;
        margin-top: 6px; margin-bottom: 6px;
      }
      .mw-title{
        font-size: 28px; font-weight: 900; letter-spacing: -0.2px;
        display:flex; align-items:center; gap:10px;
      }
      .mw-sub{
        color:#64748b; font-size: 13px; margin-top: 2px;
      }

      .mw-card{
        background:#fff; border:1px solid #e5e7eb; border-radius: 14px;
        padding: 18px 18px; box-shadow: 0 1px 2px rgba(0,0,0,0.06);
      }

      .kpi-title{
        font-size: 13px; color:#64748b; font-weight: 800;
        text-transform: uppercase; letter-spacing: .6px;
      }
      .kpi-value{
        font-size: 64px; font-weight: 950; line-height: 1.05;
        margin-top: 8px; color:#0f172a;
      }
      .kpi-unit{
        font-size: 12px; color:#94a3b8; font-weight: 700;
      }

      .mw-search{
        background:#fff; border:1px solid #e5e7eb; border-radius: 12px;
        padding: 14px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.04);
      }

      .mw-section-title{
        font-size: 18px; font-weight: 900; color:#0f172a;
        display:flex; align-items:center; gap:8px;
        margin: 0 0 10px 0;
      }
      .mw-badge{
        display:inline-block; padding: 4px 10px; border-radius: 999px;
        background:#eef2ff; color:#3730a3; border:1px solid #e0e7ff;
        font-size: 12px; font-weight: 800;
      }

      .tag-wrap{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
      .tag{
        display:inline-flex; align-items:center; gap:6px;
        padding: 6px 10px; border-radius: 999px;
        border:1px solid #e5e7eb; background:#f8fafc;
        font-size: 13px; font-weight: 800; color:#334155;
      }
      .tag-crit{
        background:#fee2e2; border:1px solid #fecaca; color:#b91c1c;
      }
      .tag-ok{
        background:#e7f8ef; border:1px solid #bbf7d0; color:#166534;
      }

      .muted{
        color:#64748b; font-size: 12px;
      }

      /* Plotly inside cards spacing */
      .plotly-chart{
        border-radius: 12px;
      }
    </style>
    """,
    unsafe_allow_html=True
)

# --------------------------------
# Header
# --------------------------------
st.markdown(
    """
    <div class="mw-header">
      <div>
        <div class="mw-title">📌 세션 대시보드</div>
        <div class="mw-sub">이탈 직전 신호 + 상담 품질을 한 눈에 관제합니다.</div>
      </div>
      <div class="muted"><b>Admin</b> 접속 중</div>
    </div>
    """,
    unsafe_allow_html=True
)

# --------------------------------
# Load sessions (전체 리스트)
# --------------------------------
sess_r = api_get("/sessions", params={"limit": 300})
sessions = sess_r.json().get("items", []) if sess_r.ok else []
if not sessions:
    st.warning("세션이 없습니다. seed를 먼저 넣어주세요.")
    st.stop()

df_sess = pd.DataFrame(sessions).sort_values("id", ascending=False)

# --------------------------------
# Search bar (필터 적용)
# --------------------------------
st.markdown('<div class="mw-search">', unsafe_allow_html=True)
search_query = st.text_input(
    "search",
    placeholder="내담자 ID, 세션 ID, 상담사 ID, 진행상태(IN_PROGRESS), 채널(CHAT) 등으로 검색",
    label_visibility="collapsed"
)
st.markdown('</div>', unsafe_allow_html=True)

df_view = df_sess.copy()
if search_query.strip():
    mask = (
        df_view.astype(str)
        .apply(lambda col: col.str.contains(search_query, case=False, na=False))
        .any(axis=1)
    )
    df_view = df_view[mask]

if df_view.empty:
    st.warning("검색 결과가 없습니다.")
    st.stop()

# 관제 대상 세션: 검색 결과 중 가장 최신(=id 큰 것)
selected_sess_id = int(df_view.iloc[0]["id"])

# --------------------------------
# Dashboard data for selected session
# --------------------------------
dash_r = api_get(f"/sessions/{selected_sess_id}/dashboard")
if not dash_r.ok:
    st.error("대시보드 데이터 로드 실패")
    st.code(dash_r.text)
    st.stop()

dash = dash_r.json() or {}

risk = float(dash.get("risk_score", 0.0) or 0.0)
quality = dash.get("quality", {}) or {}
q_score = float(quality.get("score", 0.0) or 0.0)
q_flow = float(quality.get("flow", 0.0) or 0.0)

st.markdown(f'<div class="muted">현재 관제 세션: <b>{selected_sess_id}</b> (검색 결과 최신)</div>', unsafe_allow_html=True)
st.write("")

# --------------------------------
# KPI cards (숫자 크게 + 정렬)
# --------------------------------
k1, k2, k3, k4 = st.columns([1, 1, 1, 1])

def kpi_card(title: str, value: str, color: str = "#0f172a", unit: str = ""):
    unit_html = f'<div class="kpi-unit">{unit}</div>' if unit else ""
    return f"""
      <div class="mw-card">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value" style="color:{color}">{value}</div>
        {unit_html}
      </div>
    """

risk_color = "#e11d48" if risk >= 0.7 else ("#f59e0b" if risk >= 0.4 else "#0f172a")

with k1:
    st.markdown(kpi_card("이탈 신호 (Risk)", f"{risk:.2f}", color=risk_color), unsafe_allow_html=True)

with k2:
    st.markdown(kpi_card("상담 품질", f"{q_score:.1f}", color="#2563eb"), unsafe_allow_html=True)

with k3:
    st.markdown(kpi_card("대화 흐름", f"{q_flow:.1f}", color="#7c3aed"), unsafe_allow_html=True)

# 위기 키워드: messages에서 텍스트만 합쳐서 룰 기반(우리 로직에 매칭)
msgs = dash.get("messages", []) or []
text_all = " ".join([(m.get("text") or "") for m in msgs if (m.get("text") or "").strip()])

NEGATIVE_KEYWORDS = ["그만", "힘들", "포기", "의미없", "못하겠", "지쳤", "짜증", "답답", "싫다", "괴롭", "죽고"]
detected = [kw for kw in NEGATIVE_KEYWORDS if kw in text_all]
detected = detected[:5]

with k4:
    st.markdown(
        """
        <div class="mw-card">
          <div class="kpi-title">위기 키워드</div>
          <div style="margin-top:10px" class="tag-wrap">
        """,
        unsafe_allow_html=True
    )
    if detected:
        for d in detected:
            cls = "tag tag-crit" if d in ["죽고"] else "tag"
            st.markdown(f'<span class="{cls}">#{d}</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="tag tag-ok">감지된 신호 없음</span>', unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

st.write("")

# --------------------------------
# Main layout: left(리스트) / right(분석)
# --------------------------------
left, right = st.columns([1.6, 1.0])

# ---- Left: 예약/상담 리스트 (created_at 기본 숨김)
with left:
    st.markdown('<div class="mw-card">', unsafe_allow_html=True)
    st.markdown('<div class="mw-section-title">📅 전체 예약 및 상담 리스트</div>', unsafe_allow_html=True)
    show_cols = [c for c in ["id", "counselor_id", "client_id", "channel", "progress"] if c in df_view.columns]
    st.dataframe(
        df_view[show_cols],
        use_container_width=True,
        height=360,
        hide_index=True
    )
    st.markdown('<div class="muted">※ 검색 결과만 표시됩니다. (created_at은 대시보드에서는 숨김)</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.write("")

    # Demo: 역량 분석
    st.markdown('<div class="mw-card">', unsafe_allow_html=True)
    st.markdown('<div class="mw-section-title">📊 항목별 상담 역량 분석 <span class="mw-badge">Demo</span></div>', unsafe_allow_html=True)
    demo_bar = pd.DataFrame({
        "항목": ["공감", "경청", "대처", "지속", "전문"],
        "점수": [4, 3, 5, 2, 4]
    })
    fig_bar = px.bar(demo_bar, x="항목", y="점수")
    fig_bar.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_bar, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ---- Right: 감정분포(Demo) + 위험도 추세(실데이터)
with right:
    # Demo: 감정 분포
    st.markdown('<div class="mw-card">', unsafe_allow_html=True)
    st.markdown('<div class="mw-section-title">🍩 상담 감정 분포 <span class="mw-badge">Demo</span></div>', unsafe_allow_html=True)
    demo_pie = pd.DataFrame({
        "감정": ["Positive", "Neutral", "Negative"],
        "비율": [70, 20, 10]
    })
    fig_pie = px.pie(demo_pie, values="비율", names="감정", hole=0.7)
    fig_pie.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), showlegend=True)
    st.plotly_chart(fig_pie, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.write("")

    # 위험도 추세(알럿 score)
    st.markdown('<div class="mw-card">', unsafe_allow_html=True)
    st.markdown('<div class="mw-section-title">📈 위험 지수 변동 추이</div>', unsafe_allow_html=True)

    alerts = dash.get("alerts", []) or []
    if not alerts:
        st.info("알럿 데이터가 없습니다. (내담자 메시지로 RISK_WORD 알럿을 발생시켜보세요)")
    else:
        a_df = pd.DataFrame(alerts)
        # 안전 처리
        if "at" in a_df.columns:
            a_df["at"] = pd.to_datetime(a_df["at"], errors="coerce")
        a_df["score"] = pd.to_numeric(a_df.get("score", 0.0), errors="coerce").fillna(0.0)
        a_df = a_df.sort_values("at")

        fig_line = px.line(a_df, x="at", y="score")
        fig_line.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_line, use_container_width=True)

        # 알럿 타입 분포(짧게)
        if "type" in a_df.columns:
            types = a_df["type"].value_counts().index.tolist()
            st.caption("알럿 타입: " + ", ".join(types[:6]))

    st.markdown('</div>', unsafe_allow_html=True)

st.write("")
st.info("✅ 최근 메시지/최근 알럿 표는 **세션 상세 화면(session detail ui)**에서 확인하도록 분리했습니다. (대시보드 집중도↑)")
