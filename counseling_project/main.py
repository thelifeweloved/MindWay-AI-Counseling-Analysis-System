from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()

# 스프링 부트에서 넘겨줄 데이터 구조 정의
class AnalyzeRequest(BaseModel):
    sessionId: str
    text: str
    speaker: str

@app.get("/")
def home():
    return {"message": "Wellness Analysis Server is running", "time": datetime.now()}

# 실제 분석 로직이 작동하는 구간
@app.post("/analyze")
async def analyze_sentiment(data: AnalyzeRequest):
    print(f"분석 요청 수신: [{data.sessionId}] {data.text}")
    
    # [임시 로직] 글자 수와 특정 단어로 심리 상태 분석 흉내내기
    # 나중에 여기에 KoBERT나 GPT 모델을 연결하면 됩니다.
    text_len = len(data.text)
    sentiment = "Positive" if "좋아" in data.text or "행복" in data.text else "Neutral"
    if text_len > 20:
        stress_level = "High"
    else:
        stress_level = "Low"

    return {
        "sessionId": data.sessionId,
        "sentiment": sentiment,
        "stressLevel": stress_level,
        "detectedKeywords": ["우울", "불안"] if "힘들어" in data.text else [],
        "analyzedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }