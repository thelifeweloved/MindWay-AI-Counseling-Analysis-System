import time
import random
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
st.set_page_config(page_title="MindWay · Counselor", page_icon=None, layout="wide")

# =========================================================
# 1) Global Styles (테이블 명세서 기반 전문 UI) [cite: 3, 10, 372]
# =========================================================
st.markdown(
    """
    <style>
      html, body, [class*="css"]{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      .mw-topbar{
        position: sticky; top:0; z-index:999;
        background: rgba(255,255,255,0.92);
        backdrop-filter: blur(8px);
        padding: 14px 0 12px 0;
        border-bottom: 1px solid #f0f0f0;
      }
      .mw-title{
        text-align:center; font-size: 20px; font-weight: 950;
        letter-spacing: -0.2px; color:#111827; margin: 0;
      }
      .mw-sub{
        text-align:center; font-size: 12px; color:#6b7280; margin-top: 4px;
        font-weight: 650;
      }
      .mw-wrap{max-width: 1100px; margin: 0 auto; padding: 16px 12px 120px 12px;}
      .row{display:flex; margin: 10px 0; width: 100%;}
      .left{justify-content:flex-start;}
      .right{justify-content:flex-end;}
      .bubble{
        padding: 12px 14px; border-radius: 16px;
        max-width: 74%; word-break: break-word;
        font-size: 15px; line-height: 1.45;
        box-shadow: 0 1px 2px rgba(0,0,0,0.06);
        border: 1px solid rgba(17,24,39,0.06);
      }
      .bub-counselor{
        background:#111827; color:white;
        border: 1px solid rgba(17,24,39,0.30);
      }
      .bub-client{background:#f9fafb; color:#111827;}
      .name{
        font-size: 12px; color:#6b7280;
        font-weight: 850; margin: 0 2px 4px 2px;
      }
      .meta{ font-size: 11px; color:#9ca3af; margin-top: 4px; }
      .card{
        border: 1px solid #eee; border-radius: 14px;
        padding: 12px; background: rgba(255,255,255,0.95);
        margin-bottom: 14px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
      }
      .card-title{
        font-weight: 950; margin-bottom: 10px;
        font-size: 13px; color:#111827;
      }
      .mw-inputbar{
        position: fixed; left: 50%; transform: translateX(-50%);
        bottom: 16px; width: min(820px, calc(100vw - 36px));
        background: rgba(255,255,255,0.94);
        backdrop-filter: blur(8px);
        border: 1px solid #e5e7eb;
        border-radius: 22px;
        padding: 10px 12px 10px 12px;
        box-shadow: 0 10px 26px rgba(0,0,0,0.10);
        z-index: 1000;
      }
      div[data-testid="stTextInput"] label{ display:none !important; }
      .mw-cam{
        width: 100%; aspect-ratio: 16 / 9; border-radius: 12px;
        background: linear-gradient(135deg, #0b1220, #111827);
        position: relative; overflow: hidden;
      }
      .mw-live{
        position:absolute; top:10px; left:10px;
        padding: 4px 10px; border-radius: 999px;
        background: rgba(0,0,0,0.45); color: white;
        font-size: 11px; font-weight: 800;
      }
      .mw-dot{
        width:8px; height:8px; border-radius:999px;
        background:#ef4444; box-shadow:0 0 0 3px rgba(239,68,68,0.18);
      }
      .mw-emo-row{
        display:flex; gap:10px; align-items:center;
        justify-content:space-between; margin-top: 10px;
        padding: 10px; border-radius: 12px; background: #0b1220;
      }
      .mw-emo-label{ font-size: 12px; font-weight: 900; color: white; }
      .mw-emo-score{
        font-size: 16px; font-weight: 950; color: white;
        padding: 6px 10px; border-radius: 999px;
        background: rgba(255,255,255,0.08);
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# 2) Top bar render
# =========================================================
st.markdown(
    """
    <div class="mw-topbar">
      <div class="mw-title">MindWay</div>
      <div class="mw-sub">상담사 집중 관제 모드 · 실시간 AI 보조</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# 헬스 체크 연동 (counseling_db)
api_health_check_or_stop(show_success=False)

# =========================================================
# 3) Helper functions (Business Logic)
# =========================================================
def fmt_time(x):
    if not x: return ""
    return str(x).replace("T", " ")[:19]

def last_client_text(msgs: List[Dict[str, Any]]) -> str:
    for m in reversed(msgs):
        if (m.get("speaker") or "").strip().upper() == "CLIENT":
            return (m.get("text") or "").strip()
    return ""

def last_counselor_text(msgs: List[Dict[str, Any]]) -> str:
    for m in reversed(msgs):
        if (m.get("speaker") or "").strip().upper() == "COUNSELOR":
            return (m.get("text") or "").strip()
    return ""

# 룰 기반 Fallback 엔진 (Safety Engine)
def coach_tip(text: str) -> str:
    t = (text or "").strip()
    if not t: return "내담자 발화 대기 중..."
    if any(k in t for k in ["그만", "포기", "힘들"]):
        return "⚠️ 이탈 징후: 공감 후 현재 안전 상태를 먼저 확인하세요."
    return "공감 → 구체화 질문 → 다음 행동 제안 순서로 대응하세요."

def deepface_demo_result() -> Dict[str, Any]:
    options = [
        {"emo": "안정", "emoji": "🙂", "score": 0.85},
        {"emo": "불안", "emoji": "😟", "score": 0.70},
    ]
    return random.choice(options)

# =========================================================
# 4) AI Helper UI (HyperCLOVA X 연동)
# =========================================================
def render_helper_widget(sess_id: int, counselor_id: int, msgs: List[Dict[str, Any]]):
    si = str(sess_id)
    if f"helper_input_{si}" not in st.session_state: st.session_state[f"helper_input_{si}"] = ""
    if f"helper_result_{si}" not in st.session_state: st.session_state[f"helper_result_{si}"] = None

    last_client = last_client_text(msgs)
    last_counselor = last_counselor_text(msgs)

    st.markdown("#### 💡 AI 헬퍼 (HCX-DASH-002)")
    
    col_chip1, col_chip2 = st.columns(2)
    with col_chip1:
        if st.button("공감 대응 추천", use_container_width=True, key=f"c1_{si}"):
            st.session_state[f"helper_input_{si}"] = "공감 + 구체화 질문 제안"
    with col_chip2:
        if st.button("이탈 방지 전략", use_container_width=True, key=f"c2_{si}"):
            st.session_state[f"helper_input_{si}"] = "이탈 징후 분석 및 대응 문구"

    mode = st.selectbox("모드", ["HCX", "RULE"], key=f"m_{si}", label_visibility="collapsed")
    user_req = st.text_area("요청", value=st.session_state[f"helper_input_{si}"], key=f"a_{si}", height=70, label_visibility="collapsed")
    
    if st.button("AI 조언 받기", use_container_width=True, key=f"b_{si}"):
        payload = {
            "sess_id": sess_id,
            "counselor_id": counselor_id,
            "last_client_text": last_client,
            "last_counselor_text": last_counselor,
            "context": {"mode": mode, "user_request": user_req}
        }
        r = api_post("/helper/suggestion", json=payload)
        # 백엔드의 새로운 규격(churn_signal 포함)을 세션에 저장
        st.session_state[f"helper_result_{si}"] = r.json() if r.ok else {"mode": "RULE", "suggestion": coach_tip(last_client), "churn_signal": 0}

    # === [여기서부터 시각적 로직 연동] ===
    res = st.session_state[f"helper_result_{si}"]
    if res:
        churn_val = res.get("churn_signal", 0)
        suggestion = res.get("suggestion", "")

        if churn_val == 1:
            # 1. 넛지 알림: 빨간색 경고창 (st.error)
            st.error("🚨 **이탈 위험 신호 감지**")
            # 2. 이탈 방지 전략 출력
            st.markdown(f"""
                <div style="padding:15px; border-radius:10px; border:2px solid #ef4444; background:#fef2f2;">
                    <strong style="color:#b91c1c;">💡 위기 대응 가이드:</strong><br/>
                    <span style="color:#111827;">{suggestion}</span>
                </div>
            """, unsafe_allow_html=True)
        else:
            # 정상 상황일 때
            st.info(f"💡 **AI 추천 가이드:**\n\n{suggestion}")

# =========================================================
# 5) Main Layout & Logic
# =========================================================
with st.sidebar:
    st.markdown("### 🧑‍⚕️ 상담사 제어")
    counselor_id = st.number_input("ID", min_value=1, value=1)
    consent_face = st.toggle("표정 분석 동의", value=False)
    auto_refresh = st.toggle("자동 새로고침", value=False)

# 세션 목록 (sess 테이블) [cite: 7, 60]
sess_data = api_json_or_show_error(api_get("/sessions", params={"limit": 50}))
sess_ids = sorted([s.get("id") for s in sess_data.get("items", [])], reverse=True)
sess_id = st.selectbox("현재 세션", sess_ids)

msgs = api_json_or_show_error(api_get(f"/sessions/{sess_id}/messages")).get("items", [])

left, right = st.columns([2.3, 1])

with left:
    st.markdown("<div class='mw-wrap'>", unsafe_allow_html=True)
    for m in reversed(msgs):
        speaker = (m.get("speaker") or "").strip().upper()
        text = (m.get("text") or "").strip()
        at = fmt_time(m.get("at"))
        
        # 명세서 ENUM 준수: COUNSELOR, CLIENT, SYSTEM 
        align = "right" if speaker == "COUNSELOR" else "left"
        bub_class = "bub-counselor" if speaker == "COUNSELOR" else "bub-client"
        name = "상담사" if speaker == "COUNSELOR" else "내담자"
        
        st.markdown(f"""
            <div class="row {align}">
                <div style="text-align:{align};">
                    <div class="name">{name}</div>
                    <div class="bubble {bub_class}">{text}</div>
                    <div class="meta">{at}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    # 표정 분석 (face 테이블 보조) [cite: 7, 197]
    st.markdown("<div class='card'><div class='card-title'>비언어 지표 (Face)</div>", unsafe_allow_html=True)
    if consent_face:
        res = deepface_demo_result()
        st.markdown(f"""
            <div class="mw-cam"><div class="mw-live"><span class="mw-dot"></span> LIVE</div></div>
            <div class="mw-emo-row">
                <div class="mw-emo-label">{res['emoji']} {res['emo']}</div>
                <div class="mw-emo-score">{res['score']:.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.caption("내담자 동의 시 활성화됩니다.")
    st.markdown("</div>", unsafe_allow_html=True)

    # 위험 신호 (alert 테이블) [cite: 7, 258]
    st.markdown("<div class='card'><div class='card-title'>탐지된 신호 (Alert)</div>", unsafe_allow_html=True)
    alerts = api_get(f"/sessions/{sess_id}/alerts").json().get("items", [])
    if alerts:
        for a in alerts[:3]:
            st.markdown(f"<div class='badge'>{a['type']}</div> <span class='meta'>{a['score']}</span>", unsafe_allow_html=True)
    else:
        st.caption("정상 범위 내 상담 중")
    st.markdown("</div>", unsafe_allow_html=True)

# 하단 AI 헬퍼 및 입력바
st.markdown("<div style='max-width:1100px; margin:0 auto; padding: 0 12px 10px 12px;'><div class='card'>", unsafe_allow_html=True)
render_helper_widget(sess_id, counselor_id, msgs)
st.markdown("</div></div>", unsafe_allow_html=True)

st.markdown('<div class="mw-inputbar">', unsafe_allow_html=True)
with st.form("send_form", clear_on_submit=True):
    c_text = st.text_input("msg", placeholder="상담사 메시지 입력", label_visibility="collapsed")
    if st.form_submit_button("전송", use_container_width=True):
        api_post("/messages", json={"sess_id": sess_id, "speaker": "COUNSELOR", "speaker_id": counselor_id, "text": c_text, "stt_conf": 1.0})
        st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

if auto_refresh:
    time.sleep(3)
    st.rerun()