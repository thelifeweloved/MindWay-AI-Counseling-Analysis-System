package com.counseling.service;

import com.counseling.dto.AnalysisRequest;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import java.util.Map;

@Service
public class AnalysisService {

    private final String FASTAPI_URL = "http://localhost:8000/analyze";

    // 1. 반환 타입을 void에서 Map<String, Object>로 변경합니다.
    public Map<String, Object> sendToPython(String sessionId, String text, String speaker) {
        RestTemplate restTemplate = new RestTemplate();
        AnalysisRequest request = new AnalysisRequest(sessionId, text, speaker);
        
        try {
            // 2. 결과를 변수에 담아 리턴합니다.
            @SuppressWarnings("unchecked")
            Map<String, Object> response = restTemplate.postForObject(FASTAPI_URL, request, Map.class);
            
            System.out.println("파이썬 분석 완료: " + response);
            return response; // 결과를 돌려줍니다.
            
        } catch (Exception e) {
            System.err.println("파이썬 서버 연결 실패: " + e.getMessage());
            return null; // 실패 시 null 반환
        }
    }
}