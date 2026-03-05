from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn
import httpx
import json
import asyncio
from routers.deepface import analyze_face_logic

app = FastAPI(title="MindWay Local Vision Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

MAIN_API = "http://127.0.0.1:8001/face/save"

prev_scores: dict = {}
CHANGE_THRESHOLD = 0.2  # 이 이상 변화할 때만 DB 저장

@app.websocket("/ws/analyze/{session_id}")
async def websocket_analyze(websocket: WebSocket, session_id: str):
    # 1. 클라이언트의 웹소켓 연결 요청 수락
    await websocket.accept()
    print(f"[{session_id}] 웹소켓 연결 성공")
    
    try:
        while True:
            # 2. 클라이언트로부터 0.5초마다 JSON 데이터 수신
            data_str = await websocket.receive_text()
            request_data = json.loads(data_str)
            
            image_base64 = request_data.get("image_base64")
            sess_db_id = request_data.get("sess_db_id")

            if not image_base64:
                continue

            # 3. 얼굴 분석 로직 실행 (동기 함수이므로 비동기 루프 차단을 막기 위해 쓰레드 실행)
            result = await asyncio.to_thread(analyze_face_logic, session_id, image_base64)

            # 4. 분석 성공 시 감정 변화량 체크 및 main.py로 전송
            if result.get("status") == "success" and sess_db_id:
                dominant = result["dominant"]
                score    = result["scores"].get(dominant, 0.0)
                prev     = prev_scores.get(session_id)

                # 이전 값 없거나 변화량이 THRESHOLD 이상일 때만 main.py로 HTTP 저장 요청
                if prev is None or abs(score - prev) >= CHANGE_THRESHOLD:
                    try:
                        async with httpx.AsyncClient() as client:
                            await client.post(MAIN_API, json={
                                "sess_id": int(sess_db_id),
                                "label":   dominant,
                                "score":   round(score, 2),
                                "dist":    result["scores"]
                            }, timeout=3)
                        print(f"[{session_id}] face 저장: {dominant} {score:.2f} (변화량: {abs(score - (prev or 0)):.2f})")
                    except Exception as e:
                        print(f"[{session_id}] main.py로 face 저장 실패: {e}")

                # 다음 비교를 위해 현재 점수 업데이트
                prev_scores[session_id] = score

    except WebSocketDisconnect:
        print(f"[{session_id}] 웹소켓 연결 종료 (클라이언트 이탈)")
        if session_id in prev_scores:
            del prev_scores[session_id]
            
    except Exception as e:
        print(f"[{session_id}] 웹소켓 처리 중 에러 발생: {e}")
        if session_id in prev_scores:
            del prev_scores[session_id]

@app.get("/")
async def root():
    return {"status": "ok", "mode": "OpenCV (6 Emotions) + WebSocket Enabled"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)