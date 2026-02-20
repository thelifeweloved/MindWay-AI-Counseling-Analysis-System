import streamlit as st
import requests
import os
import time
from typing import Optional, Dict, Any, List  # [필수] NameError(Optional, Dict) 해결을 위한 임포트

# =========================================================
# API Base
# - 환경변수 FRONTEND_API_URL이 있으면 우선 적용
# - 기본값: SMHRD 외부 서버 주소 (FastAPI 8000 포트)
# =========================================================
def get_api_base() -> str:
    # [수정] 외부 주소 대신 내 컴퓨터(로컬) 주소로 변경합니다.
    default_url = "http://127.0.0.1:8000" 
    return os.getenv("FRONTEND_API_URL", default_url).rstrip("/")

# =========================================================
# Low-level HTTP (공통 통신 함수)
# =========================================================
def api_get(path: str, params: Optional[Dict[str, Any]] = None, timeout: int = 6) -> requests.Response:
    base = get_api_base()
    url = f"{base}{path}"
    return requests.get(url, params=params, timeout=timeout)


def api_post(path: str, json: Optional[Dict[str, Any]] = None, timeout: int = 10) -> requests.Response:
    base = get_api_base()
    url = f"{base}{path}"
    return requests.post(url, json=json, timeout=timeout)


# =========================================================
# Response Helpers (응답 처리 및 에러 출력)
# =========================================================
def api_json_or_show_error(resp: Optional[requests.Response], title: str = "API 오류") -> Dict[str, Any]:
    """응답이 성공적이면 JSON을 반환하고, 아니면 에러를 표시한 후 중단합니다."""
    if resp is None:
        st.error(f"{title}: 응답이 없습니다.")
        st.stop()

    if not resp.ok:
        st.error(f"{title}: {resp.status_code}")
        try:
            st.code(resp.text)
        except Exception:
            st.write(resp)
        st.stop()

    try:
        return resp.json()
    except Exception as e:
        st.error(f"{title}: JSON 파싱 실패 ({e})")
        st.code(resp.text)
        st.stop()


def api_ok_or_show_error(resp: Optional[requests.Response], title: str = "API 오류") -> None:
    """단순 성공 여부(200 OK 등)만 체크합니다."""
    if resp is None:
        st.error(f"{title}: 응답이 없습니다.")
        st.stop()
    if not resp.ok:
        st.error(f"{title}: {resp.status_code}")
        st.code(resp.text)
        st.stop()


# =========================================================
# Health Check (시스템 및 DB 연결 확인)
# =========================================================
def api_health_check_or_stop(show_success: bool = True):
    """메인 대시보드 실행 전 백엔드와 DB 연결 상태를 확인합니다."""
    try:
        # main.py의 /health/db 엔드포인트를 호출합니다.
        r = api_get("/health/db", timeout=3)
        if not r.ok:
            st.error(f"API/Database 연결 실패: {r.status_code}")
            st.code(r.text)
            st.stop()

        if show_success:
            st.success("MindWay 시스템 연결 완료 (DB: counseling_db)")
        return r.json()

    except Exception as e:
        st.error(f"API 서버 연결 실패: {e}")
        st.stop()


# =========================================================
# Session Picker (sess 테이블 기반 세션 선택)
# =========================================================
@st.cache_data(ttl=3)  # 분석의 실시간성을 위해 캐시 유효 시간을 짧게 설정
def _fetch_sessions(limit: int = 200) -> Dict[str, Any]:
    """sess 테이블에서 최신 상담 목록을 가져옵니다."""
    r = api_get("/sessions", params={"limit": limit}, timeout=6)
    return api_json_or_show_error(r, title="/sessions 호출 실패")


def pick_session_id(default_id: int = 1, limit: int = 200) -> int:
    """대시보드 상단에서 분석할 sess_id를 선택하는 UI를 제공합니다."""
    data = _fetch_sessions(limit=limit)
    items = data.get("items", [])

    if not items:
        st.warning("등록된 상담 세션(sess)이 없습니다. seed.sql로 데이터를 먼저 넣어주세요.")
        sid = st.number_input("sess_id 수동 입력", min_value=1, value=default_id, step=1)
        return int(sid)

    # 테이블 명세서 기준 ID 추출 및 최신 세션순으로 정렬
    ids = [x.get("id") for x in items if x.get("id") is not None]
    if not ids:
        sid = st.number_input("sess_id 수동 입력", min_value=1, value=default_id, step=1)
        return int(sid)

    ids = sorted(ids, reverse=True)
    sid = st.selectbox("분석 및 관리 세션 선택 (sess_id)", ids, index=0)
    return int(sid)


# =========================================================
# Auto Refresh (실시간 감지용 새로고침)
# =========================================================
def auto_refresh(seconds: int = 2, enabled: bool = False):
    """지정된 시간 간격으로 페이지를 새로고침합니다."""
    if not enabled:
        return
    time.sleep(max(1, int(seconds)))
    st.rerun()