from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # ★ 추가: HTML에서 직접 API 호출 허용
from pydantic import BaseModel
from typing import Optional                          # ★ 추가: Optional 타입용
import uvicorn
import httpx                                         # ★ 추가: main.py /face/save 호출용
from routers.deepface import analyze_face_logic      # ★ 수정: vision_service → routers.deepface

app = FastAPI(title="MindWay Local Vision Server")
# 8001 서버 역할
# ★ 추가: CORS 설정 - Chat_client.html, Chat_counselor.html에서 직접 호출 가능하게
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# ★ 추가: main.py의 face 저장 엔드포인트 URL
MAIN_API = "http://127.0.0.1:8000/face/save"

# ★ 추가: 세션별 이전 감정 강도 추적 (급격한 변화 감지용)
prev_scores: dict = {}
CHANGE_THRESHOLD = 0.2  # 이 이상 변화할 때만 DB 저장

class FaceRequest(BaseModel):
    session_id:  str
    image_base64: str
    # 수정됨: timestamp 필수 규칙을 제거하고 선택 사항으로 변경하여 연동 오류 방지
    timestamp:   Optional[str] = None
    sess_db_id:  Optional[int] = None  # ★ 추가: DB의 sess.id (없으면 저장 안 함)

@app.post("/analyze")
async def analyze(request: FaceRequest):
    result = analyze_face_logic(request.session_id, request.image_base64)

    # ★ 추가: 분석 성공 + sess_db_id 있을 때만 저장 로직 실행
    if result.get("status") == "success" and request.sess_db_id:
        dominant = result["dominant"]
        score    = result["scores"].get(dominant, 0.0)
        prev     = prev_scores.get(request.session_id)

        # 이전 값 없거나 변화량이 THRESHOLD 이상일 때만 main.py로 저장 요청
        if prev is None or abs(score - prev) >= CHANGE_THRESHOLD:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(MAIN_API, json={
                        "sess_id": request.sess_db_id,
                        "label":   dominant,
                        "score":   round(score, 2),
                        "dist":    result["scores"]
                    }, timeout=3)
                print(f" face 저장: {dominant} {score:.2f} (변화량: {abs(score - (prev or 0)):.2f})")
            except Exception as e:
                print(f"face 저장 실패: {e}")

        prev_scores[request.session_id] = score

    return result

@app.get("/")
async def root():
    return {"status": "ok", "mode": "OpenCV (6 Emotions)"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)