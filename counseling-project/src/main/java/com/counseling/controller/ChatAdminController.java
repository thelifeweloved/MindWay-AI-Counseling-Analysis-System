package com.counseling.controller;

import com.counseling.entity.*;
import com.counseling.repository.*;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import java.util.*;

@RestController
@RequestMapping("/api/admin")
@RequiredArgsConstructor
public class ChatAdminController {

    private final ChatSessionRepository sessionRepo;
    private final AnalysisResultRepository analysisRepo;

    @GetMapping("/sessions")
    public Map<String, Object> sessions() {
        List<ChatSession> sessions = sessionRepo.findAll();
        
        List<Map<String, Object>> items = sessions.stream().map(s -> {
            // 해당 세션의 리포트 정보를 가져옵니다.
            String risk = analysisRepo.findBySession(s)
                    .map(AnalysisResult::getRiskLevel).orElse("N/A");
            
            // Map 앞에 <String, Object>를 추가합니다.
            return Map.<String, Object>of(
                "sessionId", s.getSessionId(),
                "status", s.getStatus(),
                "riskLevel", risk
            );
        }).toList();

        return Map.of(
            "summary", Map.of("total", sessions.size()),
            "items", items
        );
    }

    @GetMapping("/report/{sessionId}")
    public Map<String, Object> report(@PathVariable String sessionId) {
        ChatSession s = sessionRepo.findBySessionId(sessionId)
                .orElseThrow(() -> new IllegalArgumentException("세션을 찾을 수 없습니다."));
                
        AnalysisResult ar = analysisRepo.findBySession(s)
                .orElseThrow(() -> new IllegalArgumentException("아직 분석 리포트가 생성되지 않았습니다."));

        return Map.of(
            "sessionId", sessionId,
            "riskLevel", ar.getRiskLevel(),
            "evidence", ar.getEvidenceTexts() != null ? ar.getEvidenceTexts().split("\\n") : new String[]{}
        );
    }
}