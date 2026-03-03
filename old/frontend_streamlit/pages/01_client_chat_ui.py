import streamlit as st
from common_ui import api_health_check_or_stop, api_get, api_post, api_json_or_show_error

# 명세서 기반 상담 이탈 품질 분석 서비스 설정
st.set_page_config(page_title="MindWay · Client", page_icon=None, layout="wide")

# -------------------------
# 스타일 (실무 UX 안정형)
# -------------------------
st.markdown("""
<style>
.mw-title{
    text-align:center;
    font-size:24px;
    font-weight:900;
    margin-bottom:12px;
}
.mw-wrap{
    max-width:820px;
    margin:0 auto;
    padding-bottom:120px;
}
.row{display:flex; margin:10px 0;}
.left{justify-content:flex-start;}
.right{justify-content:flex-end;}
.name{
    font-size:12px;
    font-weight:800;
    margin-bottom:4px;
    opacity:0.6;
}
.time{
    font-size:11px;
    opacity:0.4;
    margin-top:3px;
}
.bubble{
    padding:10px 14px;
    border-radius:14px;
    max-width:70%;
    font-size:15px;
    line-height:1.4;
}
.client{
    background:#111827;
    color:white;
}
.counselor{
    background:#f3f4f6;
    color:#111827;
}
.input-wrap{
    position:fixed;
    bottom:15px;
    left:50%;
    transform:translateX(-50%);
    width:min(820px, calc(100vw - 40px));
    background:white;
    border:1px solid #e5e7eb;
    border-radius:18px;
    padding:10px;
    box-shadow:0 10px 25px rgba(0,0,0,0.12);
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="mw-title">MindWay</div>', unsafe_allow_html=True)

# API 및 DB 연결 상태 확인 (counseling_db)
api_health_check_or_stop(show_success=False)

# -------------------------
# 상담 방식 선택 (명세서 channel 컬럼 반영) [cite: 60, 114]
# -------------------------
# 명세서상 channel ENUM: CHAT, VOICE
mode = st.radio("상담 방식 선택", ["CHAT", "VOICE"], horizontal=True, index=0)

if mode == "VOICE":
    st.caption("🎤 음성 상담 모드 (HyperCLOVA Speech 활성화)")

# -------------------------
# 세션 관리 (sess 테이블 기반) 
# -------------------------
if "client_sess_id" not in st.session_state:
    # 가장 최근의 활성화된 세션을 가져오거나 수동 선택 로직
    r = api_get("/sessions", params={"limit": 1})
    data = api_json_or_show_error(r)
    items = data.get("items", [])
    st.session_state.client_sess_id = items[0]["id"] if items else None

sess_id = st.session_state.client_sess_id

if not sess_id:
    st.warning("진행 중인 상담 세션(sess)이 없습니다. 상담사 배정을 기다려주세요.")
    st.stop()

# -------------------------
# 메시지 로드 (msg 테이블 기반) 
# -------------------------
# 명세서에 따른 세션별 메시지 타임라인 구성
msgs_r = api_get(f"/sessions/{sess_id}/messages", params={"limit": 300})
msgs = api_json_or_show_error(msgs_r).get("items", [])

def fmt_time(x):
    if not x: return ""
    return str(x).replace("T", " ")[:19]

# -------------------------
# 메시지 렌더링
# -------------------------
st.markdown('<div class="mw-wrap">', unsafe_allow_html=True)

# 최신 메시지가 아래로 오도록 처리 (DESC로 올 경우 reversed)
for m in reversed(msgs):
    speaker = (m.get("speaker") or "").upper()
    text = m.get("text") or ""
    at = fmt_time(m.get("at"))

    # 명세서 ENUM: CLIENT [cite: 134]
    if speaker == "CLIENT":
        st.markdown(f"""
        <div class="row right">
            <div>
                <div class="name">내담자</div>
                <div class="bubble client">{text}</div>
                <div class="time">{at}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    # 명세서 ENUM: COUNSELOR [cite: 134]
    elif speaker == "COUNSELOR":
        st.markdown(f"""
        <div class="row left">
            <div>
                <div class="name">상담사</div>
                <div class="bubble counselor">{text}</div>
                <div class="time">{at}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    # SYSTEM 메시지 등 처리 [cite: 134]
    else:
        st.caption(f"System: {text} ({at})")

st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# 입력 바 (메시지 전송 및 이탈 탐지 트리거)
# -------------------------
st.markdown('<div class="input-wrap">', unsafe_allow_html=True)

with st.form("send_form", clear_on_submit=True):
    col1, col2 = st.columns([6, 1])

    with col1:
        user_text = st.text_input("msg", placeholder="메시지를 입력하세요", label_visibility="collapsed")

    with col2:
        # VOICE 모드일 경우 시각적 피드백 제공
        btn_label = "전송"
        if mode == "VOICE":
            btn_label = "🎤 전송"
        sent = st.form_submit_button(btn_label)

if sent and user_text.strip():
    # 명세서 msg 테이블 구조에 맞춘 페이로드 
    payload = {
        "sess_id": int(sess_id),
        "speaker": "CLIENT",
        "speaker_id": 1, # 실제 환경에서는 로그인된 client_id 사용
        "text": user_text,
        # 음성 모드일 경우 STT 신뢰도(stt_conf) 반영 
        "stt_conf": 0.95 if mode == "VOICE" else 1.0
    }

    # 백엔드의 /messages 엔드포인트는 이탈 신호 탐지 로직을 포함함
    r = api_post("/messages", json=payload)

    if r.ok:
        st.rerun()
    else:
        st.error("메시지 전송 실패. 네트워크 상태를 확인하세요.")

st.markdown("</div>", unsafe_allow_html=True)