import os
import requests
import streamlit as st

def get_api_base() -> str:
    # 환경변수 FRONTEND_API_URL 있으면 그거 사용, 없으면 로컬 FastAPI
    return os.getenv("FRONTEND_API_URL", "http://127.0.0.1:8000")

def api_get(path: str, params=None, timeout=5):
    base = get_api_base()
    url = f"{base}{path}"
    r = requests.get(url, params=params, timeout=timeout)
    return r

def api_post(path: str, json=None, timeout=8):
    base = get_api_base()
    url = f"{base}{path}"
    r = requests.post(url, json=json, timeout=timeout)
    return r

def api_health_check_or_stop():
    try:
        r = api_get("/health/db", timeout=3)
        if not r.ok:
            st.error(f"API 연결 실패: {r.status_code}\n{r.text}")
            st.stop()
        st.success(f"API 연결 OK: {r.json()}")
    except Exception as e:
        st.error(f"API 연결 실패: {e}")
        st.stop()

def pick_session_id(default_id: int = 1) -> int:
    """세션이 있으면 selectbox, 없으면 입력."""
    r = api_get("/sessions", params={"limit": 200})
    if not r.ok:
        st.error(f"/sessions 호출 실패: {r.status_code}\n{r.text}")
        st.stop()

    data = r.json()
    items = data.get("items", [])
    if not items:
        st.warning("등록된 세션이 없습니다. seed_min.sql/seed.sql 먼저 실행해주세요.")
        sid = st.number_input("sess_id 입력", min_value=1, value=default_id, step=1)
        return int(sid)

    ids = [x["id"] for x in items if "id" in x]
    sid = st.selectbox("세션 선택", ids, index=0)
    return int(sid)
