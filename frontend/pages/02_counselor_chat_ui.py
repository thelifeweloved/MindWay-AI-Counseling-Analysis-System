import time
import random
import streamlit as st
from common_ui import api_health_check_or_stop, api_get, api_post

st.set_page_config(page_title="Mindway Counselor Chat", page_icon="🧑‍⚕️", layout="wide")

# -------------------------
# 🎨 실무형 디자인 스타일링
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

      /* Chat bubble 위치 최종 고정 */
      .mw-wrap{max-width: 1080px; margin: 0 auto; padding: 14px 12px 110px 12px;}
      .row{display:flex; margin: 10px 0; width: 100%;}
      .left{justify-content:flex-start;}  /* 내담자: 왼쪽 */
      .right{justify-content:flex-end;}   /* 상담사: 오른쪽 */
      
      .bubble{
        padding: 12px 14px; border-radius: 16px;
        max-width: 72%; word-break: break-word;
        font-size: 15px; line-height: 1.45;
        box-shadow: 0 1px 2px rgba(0,0,0,0.06);
      }
      /* 상담사(나): Blue / 내담자: Gray */
      .bub-counselor{background:#3b82f6; color:white; text-align:left;}
      .bub-client{background:#f3f4f6; color:#1f2937; text-align:left;}
      
      .name{ font-size: 12px; color:#6b7280; font-weight: 900; margin: 0 2px 4px 2px; }
      .meta{ font-size: 11px; color:#9ca3af; margin-top: 4px; }

      /* 우측 패널 카드 디자인 */
      .card{
        border: 1px solid #eee; border-radius: 14px;
        padding: 12px; background: white; margin-bottom: 15px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
      }
      .card-title{ font-weight: 950; margin-bottom: 10px; font-size: 14px; }
      .badge{
        display:inline-block; padding: 4px 10px; border-radius: 999px;
        background:#f3f4f6; font-size: 12px; color:#374151; font-weight: 850;
      }

      /* 카메라 프레임 데모 */
      .cam{
        width: 100%; aspect-ratio: 16 / 9; border-radius: 12px;
        background: #111827; position: relative; overflow: hidden; margin-bottom: 10px;
      }
      .cam-live{
        position:absolute; top: 10px; left: 10px;
        display:flex; align-items:center; gap:8px;
        padding: 4px 10px; border-radius: 999px;
        background: rgba(0,0,0,0.5); color: white; font-size: 11px;
      }
      .dot{ width: 8px; height: 8px; border-radius: 999px; background: #ef4444; }

      /* 하단 입력바 */
      .mw-inputbar{
        position: fixed; left: 50%; transform: translateX(-50%);
        bottom: 18px; width: min(720px, calc(100vw - 40px));
        background: white; border: 1px solid #e8e8e8;
        border-radius: 26px; padding: 10px 12px 8px 12px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.10); z-index: 1000;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# 상단 바 및 API 체크
# -------------------------
st.markdown('<div class="mw-topbar"><div class="mw-title">MindWay</div><div class="mw-sub">상담사 집중 관제 모드 · 실시간 AI 보조</div></div>', unsafe_allow_html=True)
api_health_check_or_stop()

# -------------------------
# 사이드바 설정
# -------------------------
with st.sidebar:
    st.markdown("### 🧑‍⚕️ 상담사 설정")
    counselor_id = st.number_input("상담사 ID", min_value=1, value=1)
    auto_refresh = st.toggle("실시간 데이터 동기화", value=True)

# -------------------------
# 세션 선택
# -------------------------
sess_r = api_get("/sessions", params={"limit": 50})
sessions = sess_r.json().get("items", []) if sess_r.ok else []
if not sessions:
    st.warning("진행 중인 상담 세션이 없습니다.")
    st.stop()

sess_ids = [s["id"] for s in sorted(sessions, key=lambda x: x.get("id", 0), reverse=True)]
sess_id = st.selectbox("현재 상담 세션 선택", sess_ids, index=0)

# -------------------------
# 메인 레이아웃 (채팅 | 분석패널)
# -------------------------
left, right = st.columns([2.3, 1])

def fmt_time(x):
    if not x: return ""
    return str(x).replace("T", " ")[:19]

# 메시지 데이터 로드
msgs_r = api_get(f"/sessions/{sess_id}/messages", params={"limit": 300})
msgs = msgs_r.json().get("items", []) if msgs_r.ok else []

with left:
    st.markdown("<div class='mw-wrap'>", unsafe_allow_html=True)
    for m in msgs:
        speaker = (m.get("speaker") or "").upper()
        text = m.get("text") or ""
        at = fmt_time(m.get("at"))

        if speaker == "COUNSELOR":
            # 상담사(나): 오른쪽(Right)
            st.markdown(f"""
                <div class="row right"><div style="text-align:right;">
                    <div class="name">나 (상담사)</div>
                    <div class="bubble bub-counselor">{text}</div>
                    <div class="meta">{at}</div>
                </div></div>""", unsafe_allow_html=True)
        else:
            # 내담자: 왼쪽(Left)
            st.markdown(f"""
                <div class="row left"><div>
                    <div class="name">내담자</div>
                    <div class="bubble bub-client">{text}</div>
                    <div class="meta">{at}</div>
                </div></div>""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# 우측 패널 (표정 인식 & AI 가이드)
# -------------------------
with right:
    # 표정 인식 카드
    st.markdown("<div class='card'><div class='card-title'>📷 실시간 내담자 분석</div>", unsafe_allow_html=True)
    st.markdown('<div class="cam"><div class="cam-live"><span class="dot"></span> LIVE</div><div style="color:white; text-align:center; padding-top:40px; font-size:12px;">분석 중...</div></div>', unsafe_allow_html=True)
    emo, label = random.choice([("🙂", "안정"), ("😟", "불안"), ("😢", "우울"), ("😠", "짜증")]), "분석 결과"
    st.markdown(f'<div style="text-align:center;"><div style="font-size:40px;">{emo}</div><div class="badge">{label}</div></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # AI 코칭 카드
    st.markdown("<div class='card'><div class='card-title'>💡 AI 개입 전략</div>", unsafe_allow_html=True)
    st.info("내담자의 말에 공감을 표시하고 구체적인 상황을 질문해보세요.")
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# 하단 메시지 입력
# -------------------------
st.markdown('<div class="mw-inputbar">', unsafe_allow_html=True)
with st.form("send_form", clear_on_submit=True):
    counselor_text = st.text_input("메시지", placeholder="메시지를 입력하세요", label_visibility="collapsed")
    sent = st.form_submit_button("전송", use_container_width=True)

if sent and counselor_text.strip():
    api_post("/messages", json={"sess_id": int(sess_id), "speaker": "COUNSELOR", "speaker_id": int(counselor_id), "text": counselor_text.strip()})
    st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

if auto_refresh:
    time.sleep(2)
    st.rerun()