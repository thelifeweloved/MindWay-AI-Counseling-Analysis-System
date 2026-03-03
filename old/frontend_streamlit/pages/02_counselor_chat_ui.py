import time
import streamlit as st
from typing import List, Dict, Any

from common_ui import (
    api_health_check_or_stop,
    api_get,
    api_post,
    api_json_or_show_error,
)

# =========================================================
# 0) Page config
# =========================================================
st.set_page_config(page_title="MindWay · Counselor", layout="wide")

# =========================================================
# 1) Styles
# =========================================================
st.markdown("""
<style>
  html, body, [class*="css"]{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  .mw-topbar{
    position:sticky; top:0; z-index:999;
    background:rgba(255,255,255,0.92); backdrop-filter:blur(8px);
    padding:14px 0 12px 0; border-bottom:1px solid #f0f0f0;
  }
  .mw-title{ text-align:center; font-size:20px; font-weight:950;
    letter-spacing:-0.2px; color:#111827; margin:0; }
  .mw-sub{ text-align:center; font-size:12px; color:#6b7280;
    margin-top:4px; font-weight:650; }
  .mw-wrap{ max-width:1100px; margin:0 auto; padding:16px 12px 120px 12px; }
  .row{ display:flex; margin:10px 0; width:100%; }
  .left{ justify-content:flex-start; }
  .right{ justify-content:flex-end; }
  .bubble{ padding:12px 14px; border-radius:16px; max-width:74%;
    word-break:break-word; font-size:15px; line-height:1.45;
    box-shadow:0 1px 2px rgba(0,0,0,0.06);
    border:1px solid rgba(17,24,39,0.06); }
  .bub-counselor{ background:#111827; color:white;
    border:1px solid rgba(17,24,39,0.30); }
  .bub-client{ background:#f9fafb; color:#111827; }
  .name{ font-size:12px; color:#6b7280; font-weight:850;
    margin:0 2px 4px 2px; }
  .meta{ font-size:11px; color:#9ca3af; margin-top:4px; }
  .card{ border:1px solid #eee; border-radius:14px; padding:12px;
    background:rgba(255,255,255,0.95); margin-bottom:14px;
    box-shadow:0 1px 2px rgba(0,0,0,0.04); }
  .card-title{ font-weight:950; margin-bottom:10px;
    font-size:13px; color:#111827; }
  .mw-inputbar{
    position:fixed; left:50%; transform:translateX(-50%);
    bottom:16px; width:min(820px, calc(100vw - 36px));
    background:rgba(255,255,255,0.94); backdrop-filter:blur(8px);
    border:1px solid #e5e7eb; border-radius:22px;
    padding:10px 12px;
    box-shadow:0 10px 26px rgba(0,0,0,0.10); z-index:1000;
  }
  div[data-testid="stTextInput"] label{ display:none !important; }
  .mw-cam{ width:100%; aspect-ratio:16/9; border-radius:12px;
    background:linear-gradient(135deg,#0b1220,#111827);
    position:relative; overflow:hidden; }
  .mw-live{ position:absolute; top:10px; left:10px;
    padding:4px 10px; border-radius:999px;
    background:rgba(0,0,0,0.45); color:white;
    font-size:11px; font-weight:800; }
  .mw-dot{ width:8px; height:8px; border-radius:999px;
    background:#ef4444; box-shadow:0 0 0 3px rgba(239,68,68,0.18);
    display:inline-block; }
  .mw-emo-row{ display:flex; gap:10px; align-items:center;
    justify-content:space-between; margin-top:10px;
    padding:10px; border-radius:12px; background:#0b1220; }
  .mw-emo-label{ font-size:12px; font-weight:900; color:white; }
  .mw-emo-score{ font-size:16px; font-weight:950; color:white;
    padding:6px 10px; border-radius:999px;
    background:rgba(255,255,255,0.08); }
  .sugg-card{ background:#f8fafc; border:1px solid #e2e8f0;
    border-radius:8px; padding:10px 12px; margin-bottom:8px; }
  .sugg-type{ font-size:11px; font-weight:900; color:#6366f1;
    text-transform:uppercase; margin-bottom:4px; }
  .sugg-direction{ font-size:13px; color:#1e293b; line-height:1.5; }
  .sugg-rationale{ font-size:11px; color:#94a3b8; margin-top:3px; }
  .risk-high{ background:#fef2f2; border:2px solid #ef4444;
    border-radius:10px; padding:12px; margin:8px 0; }
  .risk-caution{ background:#fffbeb; border:2px solid #f59e0b;
    border-radius:10px; padding:12px; margin:8px 0; }
  .risk-normal{ background:#f0fdf4; border:2px solid #22c55e;
    border-radius:10px; padding:12px; margin:8px 0; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# 2) Top bar
# =========================================================
st.markdown("""
<div class="mw-topbar">
  <div class="mw-title">MindWay</div>
  <div class="mw-sub">상담사 집중 관제 모드 · 실시간 AI 보조</div>
</div>
""", unsafe_allow_html=True)

api_health_check_or_stop(show_success=False)

# =========================================================
# 3) 유틸 함수
# =========================================================
def fmt_time(x):
    if not x:
        return ""
    return str(x).replace("T", " ")[:19]


def get_last_client_text(msgs: List[Dict[str, Any]]) -> str:
    for m in reversed(msgs):
        if (m.get("speaker") or "").strip().upper() == "CLIENT":
            return (m.get("text") or "").strip()
    return ""


def get_last_counselor_text(msgs: List[Dict[str, Any]]) -> str:
    for m in reversed(msgs):
        if (m.get("speaker") or "").strip().upper() == "COUNSELOR":
            return (m.get("text") or "").strip()
    return ""


def build_history(msgs: List[Dict[str, Any]], n: int = 4) -> List[Dict[str, str]]:
    """helper.py history 파라미터용: 최근 n개 발화 추출"""
    result = []
    for m in msgs[-n:]:
        spk = (m.get("speaker") or "").strip().upper()
        txt = (m.get("text") or "").strip()
        if txt:
            result.append({
                "role": "counselor" if spk == "COUNSELOR" else "client",
                "text": txt,
            })
    return result

# =========================================================
# 4) AI 헬퍼 위젯 — helper.py v2 응답 규격 완전 반영
#    응답 키: mode, churn_signal, type,
#             insight, emotions, intent, risk, suggestions
# =========================================================
def render_helper_widget(sess_id: int, counselor_id: int, msgs: List[Dict[str, Any]]):
    si = str(sess_id)

    if f"helper_result_{si}" not in st.session_state:
        st.session_state[f"helper_result_{si}"] = None

    last_client    = get_last_client_text(msgs)
    last_counselor = get_last_counselor_text(msgs)
    history        = build_history(msgs, n=4)

    st.markdown("#### AI 헬퍼 (HCX-DASH-002)")

    col1, col2 = st.columns(2)
    with col1:
        run_btn = st.button("실시간 분석 요청", use_container_width=True, key="helper_run_" + si)
    with col2:
        clear_btn = st.button("초기화", use_container_width=True, key="helper_clear_" + si)

    if clear_btn:
        st.session_state[f"helper_result_{si}"] = None

    if run_btn:
        if not last_client:
            st.warning("아직 내담자 발화가 없습니다.")
        else:
            with st.spinner("HCX 분석 중..."):
                payload = {
                    "sess_id":             sess_id,
                    "counselor_id":        counselor_id,
                    "last_client_text":    last_client,
                    "last_counselor_text": last_counselor,
                    "history":             history,
                }
                r = api_post("/helper/suggestion", json=payload)
                if r and r.ok:
                    st.session_state[f"helper_result_{si}"] = r.json()
                else:
                    # API 실패 시 안전 fallback
                    st.session_state[f"helper_result_{si}"] = {
                        "mode": "FALLBACK",
                        "churn_signal": 0,
                        "type": "NORMAL",
                        "insight": "API 연결 실패 — 네트워크 또는 서버 상태를 확인하세요.",
                        "emotions": [],
                        "intent": "",
                        "risk": {"level": "Caution", "signals": [], "message": "서버 응답 없음"},
                        "suggestions": [],
                    }

    # ── 결과 렌더링 ──────────────────────────────────────
    res = st.session_state[f"helper_result_{si}"]
    if not res:
        st.caption("분석 버튼을 누르면 현재 내담자 발화를 AI가 분석합니다.")
        return

    churn_signal = res.get("churn_signal", 0)
    risk         = res.get("risk") or {}
    risk_level   = risk.get("level", "Normal")
    risk_msg     = risk.get("message", "")
    risk_signals = risk.get("signals") or []
    mode         = res.get("mode", "")

    # ── 위험 배너 ────────────────────────────────────────
    if risk_level == "High" or churn_signal == 1:
        st.error("🚨 고위험 신호 감지 — 즉각적인 안전 확인이 필요합니다")
        risk_css  = "risk-high"
        risk_icon = "🔴"
    elif risk_level == "Caution":
        st.warning("⚠️ 주의 신호 감지")
        risk_css  = "risk-caution"
        risk_icon = "🟡"
    else:
        risk_css  = "risk-normal"
        risk_icon = "🟢"

    sig_str = " / ".join(risk_signals) if risk_signals else "없음"
    st.markdown(
        "<div class='" + risk_css + "'>"
        "<b>" + risk_icon + " " + risk_level + "</b>&nbsp;&nbsp;" + risk_msg
        + "<br/><span style='font-size:12px;color:#64748b;'>신호 근거: " + sig_str + "</span>"
        + "</div>",
        unsafe_allow_html=True,
    )

    # ── 인사이트 ─────────────────────────────────────────
    insight  = res.get("insight", "")
    emotions = res.get("emotions") or []
    intent   = res.get("intent", "")

    st.markdown("**인사이트**")
    st.info(insight or "-")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**감지 감정**")
        st.caption(" · ".join(emotions) if emotions else "-")
    with col_b:
        st.markdown("**추정 의도**")
        st.caption(intent or "-")

    # ── 개입 방향 제안 (suggestions) ─────────────────────
    suggestions = res.get("suggestions") or []
    if suggestions:
        st.markdown("**개입 방향 제안**")
        for s in suggestions:
            if not isinstance(s, dict):
                continue
            type_label = s.get("type", "")
            direction  = s.get("direction", s.get("text", ""))
            rationale  = s.get("rationale", "")
            st.markdown(
                "<div class='sugg-card'>"
                "<div class='sugg-type'>" + type_label + "</div>"
                "<div class='sugg-direction'>" + direction + "</div>"
                + ("<div class='sugg-rationale'>근거: " + rationale + "</div>" if rationale else "")
                + "</div>",
                unsafe_allow_html=True,
            )

    if mode in ("FALLBACK", "RULE", "RULE_ONLY"):
        st.caption("⚠️ 모드: " + mode + " (HCX 미사용 또는 오류 — .env의 USE_HCX=1 확인)")

# =========================================================
# 5) Sidebar
# =========================================================
with st.sidebar:
    st.markdown("### 상담사 제어")
    counselor_id = st.number_input("상담사 ID", min_value=1, value=1)
    consent_face = st.toggle("표정 분석 동의", value=False)
    auto_refresh = st.toggle("자동 새로고침 (3s)", value=False)

# =========================================================
# 6) 세션 선택
# =========================================================
sess_raw  = api_json_or_show_error(api_get("/sessions", params={"limit": 50}))
sess_items = sess_raw.get("items", []) if sess_raw else []
sess_ids   = sorted([s.get("id") for s in sess_items if s.get("id")], reverse=True)

if not sess_ids:
    st.warning("세션이 없습니다. seed.sql을 먼저 실행하거나 새 세션을 생성하세요.")
    st.stop()

sess_id = st.selectbox("현재 세션", sess_ids)
msgs_raw = api_json_or_show_error(api_get(f"/sessions/{sess_id}/messages"))
msgs     = msgs_raw.get("items", []) if msgs_raw else []

# =========================================================
# 7) 메인 레이아웃
# =========================================================
left, right = st.columns([2.3, 1])

with left:
    st.markdown("<div class='mw-wrap'>", unsafe_allow_html=True)
    for m in reversed(msgs):
        speaker   = (m.get("speaker") or "").strip().upper()
        text      = (m.get("text") or "").strip()
        at        = fmt_time(m.get("at"))
        align     = "right" if speaker == "COUNSELOR" else "left"
        bub_class = "bub-counselor" if speaker == "COUNSELOR" else "bub-client"
        name      = "상담사" if speaker == "COUNSELOR" else "내담자"
        st.markdown(
            "<div class='row " + align + "'>"
            "<div style='text-align:" + align + ";'>"
            "<div class='name'>" + name + "</div>"
            "<div class='bubble " + bub_class + "'>" + text + "</div>"
            "<div class='meta'>" + at + "</div>"
            "</div></div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    # ── 표정 분석 (DeepFace 라우터 연동 대기) ───────────
    st.markdown("<div class='card'><div class='card-title'>비언어 지표 (Face)</div>", unsafe_allow_html=True)
    if consent_face:
        # DeepFace 라우터 완성 시 아래 한 줄로 교체:
        # face_res = api_get(f"/face/{sess_id}/latest")
        # face_data = face_res.json() if face_res and face_res.ok else {}
        st.markdown(
            "<div class='mw-cam'>"
            "<div class='mw-live'><span class='mw-dot'></span>&nbsp;LIVE</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.caption("DeepFace 라우터 연동 대기 중 — 완성 후 자동 활성화")
    else:
        st.caption("내담자 동의 시 활성화됩니다.")
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Alert 목록 ───────────────────────────────────────
    st.markdown("<div class='card'><div class='card-title'>탐지된 신호 (Alert)</div>", unsafe_allow_html=True)
    alert_r = api_get(f"/sessions/{sess_id}/alerts")
    alerts  = (alert_r.json().get("items", []) if alert_r and alert_r.ok else [])
    if alerts:
        for a in alerts[:5]:
            a_type  = str(a.get("type", ""))
            a_score = str(a.get("score", ""))
            a_at    = fmt_time(a.get("at", ""))
            st.markdown(
                "<div style='font-size:12px;padding:4px 0;"
                "border-bottom:1px solid #f3f4f6;'>"
                "<b>" + a_type + "</b>"
                "<span style='color:#9ca3af;margin-left:8px;'>" + a_score + "</span>"
                "<span style='color:#d1d5db;margin-left:8px;font-size:11px;'>" + a_at + "</span>"
                "</div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("정상 범위 내 상담 중")
    st.markdown("</div>", unsafe_allow_html=True)

    # ── AI 헬퍼 위젯 ─────────────────────────────────────
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    render_helper_widget(sess_id, counselor_id, msgs)
    st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# 8) 하단 입력바
# =========================================================
st.markdown("<div class='mw-inputbar'>", unsafe_allow_html=True)
with st.form("send_form", clear_on_submit=True):
    c_text = st.text_input("msg", placeholder="상담사 메시지 입력", label_visibility="collapsed")
    if st.form_submit_button("전송", use_container_width=True):
        if c_text.strip():
            api_post(
                "/messages",
                json={
                    "sess_id":    sess_id,
                    "speaker":    "COUNSELOR",
                    "speaker_id": counselor_id,
                    "text":       c_text.strip(),
                    "stt_conf":   1.0,
                },
            )
            st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# 9) 자동 새로고침
# =========================================================
if auto_refresh:
    time.sleep(3)
    st.rerun()