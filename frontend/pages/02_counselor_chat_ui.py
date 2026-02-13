import time
import random
import streamlit as st
from common_ui import api_health_check_or_stop, api_get, api_post

st.set_page_config(page_title="Mindway Counselor Chat", page_icon="🧑‍⚕️", layout="wide")

# -------------------------
# 🎨 실무형 디자인 스타일링 (정렬 로직 강화)
# -------------------------
st.markdown(
    """
    <style>
      .mw-topbar{
        position: sticky; top:0; z-index:999;
        background:white; padding: 14px 0 12px 0;
        border-bottom: 1px solid #f0f0f0;
      }
      .mw-title{
        text-align:center; font-size: 28px; font-weight: 950;
        letter-spacing: 0.2px; margin-top: 2px;
      }
      .mw-sub{
        text-align:center; font-size: 12px; color:#6b7280; margin-top: 4px;
      }

      /* Chat bubble 영역: 자식 요소들이 가로 전체를 쓰도록 설정 */
      .mw-wrap{
          max-width: 1080px; 
          margin: 0 auto; 
          padding: 14px 12px 110px 12px;
          display: flex;
          flex-direction: column;
      }
      
      /* 메시지 한 줄 영역 */
      .chat-row{
          display: flex;
          width: 100%;
          margin: 10px 0;
      }
      
      /* ✅ 상담사(나): 오른쪽 정렬 강제 */
      .counselor-row {
          justify-content: flex-end;
      }
      
      /* ✅ 내담자: 왼쪽 정렬 강제 */
      .client-row {
          justify-content: flex-start;
      }

      .bubble{
        padding: 12px 14px; border-radius: 16px;
        max-width: 70%; word-break: break-word;
        font-size: 15px; line-height: 1.45;
        box-shadow: 0 1px 2px rgba(0,0,0,0.06);
      }
      
      /* 상담사(나): Blue / 내담자: Gray */
      .bub-counselor{background:#3b82f6; color:white;}
      .bub-client{background:#f3f4f6; color:#1f2937;}
      
      .name{ font-size: 12px; color:#6b7280; font-weight: 900; margin-bottom: 4px; }
      .meta{ font-size: 11px; color:#9ca3af; margin-top: 4px; }

      /* 우측 패널 및 기타 스타일 */
      .card{ border: 1px solid #eee; border-radius: 14px; padding: 12px; background: white; margin-bottom: 15px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
      .cam{ width: 100%; aspect-ratio: 16 / 9; border-radius: 12px; background: #111827; position: relative; overflow: hidden; margin-bottom: 10px; }
      .mw-inputbar{ position: fixed; left: 50%; transform: translateX(-50%); bottom: 18px; width: min(720px, calc(100vw - 40px)); background: white; border: 1px solid #e8e8e8; border-radius: 26px; padding: 10px 12px 8px 12px; box-shadow: 0 6px 18px rgba(0,0,0,0.10); z-index: 1000; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="mw-topbar"><div class="mw-title">MindWay</div><div class="mw-sub">상담사 관제 모드</div></div>', unsafe_allow_html=True)
api_health_check_or_stop()

with st.sidebar:
    st.markdown("### 🧑‍⚕️ 상담사 설정")
    counselor_id = st.number_input("상담사 ID", min_value=1, value=1)
    auto_refresh = st.toggle("실시간 데이터 동기화", value=True)

sess_r = api_get("/sessions", params={"limit": 50})
sessions = sess_r.json().get("items", []) if sess_r.ok else []
if not sessions: st.stop()

sess_ids = [s["id"] for s in sorted(sessions, key=lambda x: x.get("id", 0), reverse=True)]
sess_id = st.selectbox("현재 상담 세션 선택", sess_ids, index=0)

left, right = st.columns([2.3, 1])

def fmt_time(x):
    if not x: return ""
    return str(x).replace("T", " ")[:16]

msgs_r = api_get(f"/sessions/{sess_id}/messages", params={"limit": 300})
msgs = msgs_r.json().get("items", []) if msgs_r.ok else []

with left:
    st.markdown("<div class='mw-wrap'>", unsafe_allow_html=True)
    for m in msgs:
        speaker = (m.get("speaker") or "").upper()
        text = m.get("text") or ""
        at = fmt_time(m.get("at"))

        if speaker == "COUNSELOR":
            # ✅ 상담사: 오른쪽(counselor-row) 배치 강제
            st.markdown(f"""
                <div class="chat-row counselor-row">
                    <div style="display: flex; flex-direction: column; align-items: flex-end;">
                        <div class="name">나 (상담사)</div>
                        <div class="bubble bub-counselor">{text}</div>
                        <div class="meta">{at}</div>
                    </div>
                </div>""", unsafe_allow_html=True)
        else:
            # ✅ 내담자: 왼쪽(client-row) 배치 강제
            st.markdown(f"""
                <div class="chat-row client-row">
                    <div style="display: flex; flex-direction: column; align-items: flex-start;">
                        <div class="name">내담자</div>
                        <div class="bubble bub-client">{text}</div>
                        <div class="meta">{at}</div>
                    </div>
                </div>""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown("<div class='card'><b>📷 실시간 내담자 분석</b>", unsafe_allow_html=True)
    st.markdown('<div class="cam"></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div class='card'><b>💡 AI 개입 전략</b>", unsafe_allow_html=True)
    st.info("내담자의 말에 공감을 표시해보세요.")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="mw-inputbar">', unsafe_allow_html=True)
with st.form("send_form", clear_on_submit=True):
    counselor_text = st.text_input("메시지", placeholder="메시지 입력...", label_visibility="collapsed")
    sent = st.form_submit_button("전송", use_container_width=True)

if sent and counselor_text.strip():
    api_post("/messages", json={"sess_id": int(sess_id), "speaker": "COUNSELOR", "speaker_id": int(counselor_id), "text": counselor_text.strip()})
    st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

if auto_refresh:
    time.sleep(2)
    st.rerun()