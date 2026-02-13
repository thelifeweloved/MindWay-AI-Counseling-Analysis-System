import streamlit as st
from common_ui import api_health_check_or_stop, api_get, api_post

# --------------------------------
# Page config
# --------------------------------
st.set_page_config(page_title="Client Chat", page_icon="💬", layout="wide")

# --------------------------------
# Top bar + Styles
# --------------------------------
st.markdown(
    """
    <style>
      /* Top bar */
      .mw-topbar{
        position: sticky;
        top: 0;
        z-index: 999;
        background: white;
        padding: 10px 0 12px 0;
        border-bottom: 1px solid #f0f0f0;
      }
      .mw-title{
        text-align:center;
        font-size: 20px;
        font-weight: 800;
        letter-spacing: 0.2px;
      }

      /* Main content wrap */
      .mw-wrap{
        max-width: 880px;
        margin: 0 auto;
        padding: 14px 12px 140px 12px; /* bottom padding for input bar */
      }

      /* Chat bubbles */
      .row{display:flex; margin: 10px 0;}
      .left{justify-content:flex-start;}
      .right{justify-content:flex-end;}
      .bubble{
        padding: 12px 14px;
        border-radius: 16px;
        max-width: 72%;
        word-break: break-word;
        font-size: 15px;
        line-height: 1.45;
        box-shadow: 0 1px 2px rgba(0,0,0,0.06);
      }
      .bub-counselor{background:#f3f4f6;}
      .bub-client{background:#dbeafe;}
      .name{
        font-size: 12px;
        color:#6b7280;
        font-weight: 700;
        margin: 0 2px 4px 2px;
      }
      .meta{
        font-size: 11px;
        color:#9ca3af;
        margin-top: 4px;
      }

      /* Bottom input bar (ChatGPT-like) */
      .mw-inputbar{
        position: fixed;
        left: 50%;
        transform: translateX(-50%);
        bottom: 18px;
        width: min(880px, calc(100vw - 40px));
        background: white;
        border: 1px solid #e8e8e8;
        border-radius: 26px;
        padding: 10px 12px 8px 12px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.10);
        z-index: 1000;
      }
      .mw-inputbar .hint{
        font-size: 12px;
        color:#9ca3af;
        text-align:center;
        margin-top: 8px;
      }

      /* Streamlit TextInput styling */
      div[data-testid="stTextInput"] input{
        border-radius: 18px !important;
        border: 1px solid #e5e7eb !important;
        padding: 12px 12px !important;
        height: 44px !important;
      }
      div[data-testid="stTextInput"] label{
        display:none !important;
      }

      .mw-mini{
        font-size: 14px;
        color: #9ca3af;
        font-weight: 800;
        padding-top: 6px;
      }
    </style>

    <div class="mw-topbar">
      <div class="mw-title">MindWay</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------------------------
# API health (stop if down)
# --------------------------------
api_health_check_or_stop()

# --------------------------------
# Session auto-pick (latest)
# - 내담자 화면에는 세션선택/위험도/알럿 표시 안 함
# --------------------------------
if "client_sess_id" not in st.session_state:
    r = api_get("/sessions", params={"limit": 1})
    items = r.json().get("items", []) if r.ok else []
    st.session_state.client_sess_id = items[0]["id"] if items else None

sess_id = st.session_state.client_sess_id
if not sess_id:
    st.warning("현재 연결된 상담 세션이 없습니다. (테스트 데이터가 필요해요)")
    st.stop()

def fmt_time(x):
    if not x:
        return ""
    try:
        return str(x).replace("T", " ")[:19]
    except Exception:
        return str(x)

# --------------------------------
# Messages render (center big)
# --------------------------------
msgs_r = api_get(f"/sessions/{sess_id}/messages", params={"limit": 300})
msgs = msgs_r.json().get("items", []) if msgs_r.ok else []

st.markdown('<div class="mw-wrap">', unsafe_allow_html=True)

for m in msgs:
    speaker = (m.get("speaker") or "").upper()
    text = m.get("text") or ""
    at = fmt_time(m.get("at"))

    # 상담사 왼쪽 / 내담자 오른쪽
    if speaker == "COUNSELOR":
        st.markdown(
            f"""
            <div class="row left">
              <div>
                <div class="name">상담사</div>
                <div class="bubble bub-counselor">{text}</div>
                <div class="meta">{at}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    elif speaker == "CLIENT":
        st.markdown(
            f"""
            <div class="row right">
              <div>
                <div class="name" style="text-align:right;">내담자</div>
                <div class="bubble bub-client">{text}</div>
                <div class="meta" style="text-align:right;">{at}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"""
            <div class="row left">
              <div>
                <div class="name">SYSTEM</div>
                <div class="bubble bub-counselor">{text}</div>
                <div class="meta">{at}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )

st.markdown("</div>", unsafe_allow_html=True)

# --------------------------------
# Bottom input bar (fixed)
# --------------------------------
st.markdown('<div class="mw-inputbar">', unsafe_allow_html=True)

with st.form("send_form", clear_on_submit=True):
    user_text = st.text_input("메시지", placeholder="무엇이든 물어보세요", label_visibility="collapsed")

    c1, c2, c3 = st.columns([1, 6, 2])
    with c1:
        # UI 느낌용 + (기능은 아직 안 붙임)
        st.markdown('<div class="mw-mini">＋</div>', unsafe_allow_html=True)
    with c2:
        st.write("")  # spacing
    with c3:
        sent = st.form_submit_button("전송", use_container_width=True)

if sent:
    if not user_text.strip():
        st.warning("메시지를 입력하세요.")
        st.stop()

    payload = {
        "sess_id": int(sess_id),
        "speaker": "CLIENT",
        "speaker_id": 1,
        "text": user_text.strip()
    }
    resp = api_post("/messages", json=payload)

    if resp.ok:
        st.rerun()
    else:
        st.error(f"전송 실패: {resp.status_code}")
        st.code(resp.text)

st.markdown(
    """
    <div class="hint">
      ChatGPT는 실수를 할 수 있습니다. 중요한 정보는 재차 확인하세요.
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("</div>", unsafe_allow_html=True)
