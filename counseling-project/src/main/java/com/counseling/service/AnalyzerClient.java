package com.counseling.service; 

import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import java.util.Map;

@Service
public class AnalyzerClient {
    // 스프링에서 외부 API(파이썬)를 호출할 때 사용하는 도구입니다.
    private final RestTemplate restTemplate = new RestTemplate();
    
    // 가이드 문서상의 파이썬 서버 주소 (8000포트) [cite: 90, 445]
    private final String baseUrl = "http://localhost:8000"; 

    public Map<String, Object> analyzeSession(String sessionId) {
        // 파이썬 FastAPI의 분석 엔드포인트를 호출합니다. [cite: 275]
        return restTemplate.postForObject(baseUrl + "/analyze/" + sessionId, null, Map.class);
    }
}