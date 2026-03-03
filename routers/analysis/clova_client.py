# services/clova_client.py
# CLOVA X(대화형 LLM) 호출 클라이언트
# ✅ 재시도 로직 추가 (429 Too Many Requests 대응)

import time
import requests


class ClovaXClient:
    def __init__(self, api_key: str, endpoint_id: str, app: str = "testapp"):
        self.api_key = api_key
        self.endpoint_id = endpoint_id
        self.app = app
        self.url = f"https://clovastudio.stream.ntruss.com/{app}/v3/chat-completions/{endpoint_id}"

    def chat(
        self,
        system_text: str,
        user_text: str,
        temperature: float = 0.2,
        timeout: int = 60,
        max_retries: int = 3,       # 최대 재시도 횟수
        retry_wait: int = 15,       # 429 시 대기 시간(초)
    ) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "messages": [
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_text},
            ],
            "temperature": temperature,
            "maxTokens": 1024,      # ✅ 토큰 한도 명시
        }

        last_resp = None
        for attempt in range(max_retries):
            last_resp = requests.post(self.url, headers=headers, json=payload, timeout=timeout)

            # ✅ 429: 잠깐 기다렸다가 재시도
            if last_resp.status_code == 429:
                wait = retry_wait * (attempt + 1)   # 15초, 30초, 45초
                time.sleep(wait)
                continue

            last_resp.raise_for_status()
            return last_resp.json()

        # 3번 다 실패하면 마지막 응답으로 에러 발생
        last_resp.raise_for_status()
        return last_resp.json()
