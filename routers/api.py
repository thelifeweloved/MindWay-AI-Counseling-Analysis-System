# routers/api.py
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db import get_db                                        # ✅ 경로 수정
from routers.analysis.runner import run_core_features        # ✅ 경로 수정
from routers.analysis.clova_client import ClovaXClient       # ✅ 경로 수정


api_router = APIRouter(prefix="/api", tags=["api"])


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None or str(v).strip() == "":
        return default
    return v


def _build_clova_client() -> ClovaXClient:
    api_key = _env("CLOVA_API_KEY")
    endpoint_id = _env("CLOVA_ENDPOINT_ID")
    app = _env("CLOVA_APP", "testapp")

    if not api_key or not endpoint_id:
        raise HTTPException(
            status_code=500,
            detail="CLOVA_API_KEY / CLOVA_ENDPOINT_ID 환경변수가 필요합니다.",
        )

    return ClovaXClient(api_key=api_key, endpoint_id=endpoint_id, app=app)


@api_router.get("/health")
def health():
    return {"ok": True}


# ✅ sess_id는 URL path로 받고, body는 없음
@api_router.post("/sessions/{sess_id}/analysis")
def run_core(
    sess_id: int,
    db: Session = Depends(get_db),
):
    """
    프론트에서 호출:
      POST /api/sessions/1/analysis
    """
    clova_client = _build_clova_client()

    try:
        result = run_core_features(
            clova_client,
            sess_id=sess_id,
            db=db,
        )
        db.commit()
        return {"ok": True, "result": result}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"run_core_features 실패: {e}")
