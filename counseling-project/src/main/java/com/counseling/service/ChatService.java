package com.counseling.service;

import com.counseling.dto.*;
import com.counseling.entity.*;
import com.counseling.repository.*;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class ChatService {

    private final ChatSessionRepository sessionRepo;
    private final ChatMessageRepository messageRepo;
    private final AnalysisService analysisService; 
    private final AnalysisResultRepository analysisRepo; 

    @Transactional
    public ChatSession getOrCreateSession(String sessionId) {
        return sessionRepo.findBySessionId(sessionId).orElseGet(() -> {
            ChatSession s = ChatSession.builder()
                    .sessionId(sessionId)
                    .status("ACTIVE")
                    .mode("BOT")
                    .build();
            return sessionRepo.save(s);
        });
    }

    @Transactional
    public ChatBroadcast saveAndBuildBroadcast(ChatSendRequest req) {
        ChatSession session = getOrCreateSession(req.getSessionId());
        
        List<ChatMessage> msgs = messageRepo.findBySessionOrderBySeqAsc(session);
        int nextSeq = msgs.size() + 1;

        ChatMessage m = ChatMessage.builder()
                .session(session)
                .speaker(req.getSpeaker())
                .seq(nextSeq)
                .text(req.getText())
                .build();
        messageRepo.save(m); // DB에 메시지 먼저 저장

        session.setLastMsgAt(LocalDateTime.now());

        // 2. 파이썬 호출 및 결과 저장을 하나의 블록으로 합칩니다.
        if ("CLIENT".equalsIgnoreCase(req.getSpeaker())) {
            session.setLastClientMsgAt(LocalDateTime.now());
            
            // 파이썬 서버로부터 분석 결과 수신
            Map<String, Object> res = analysisService.sendToPython(session.getSessionId(), req.getText(), req.getSpeaker());
            
            if (res != null) {
                // 기존 리포트가 있으면 가져오고 없으면 생성
                AnalysisResult ar = analysisRepo.findBySession(session)
                        .orElse(AnalysisResult.builder().session(session).build());

                // 데이터 매핑 및 저장
                ar.setRiskLevel((String) res.getOrDefault("sentiment", "Neutral")); 
                ar.setRiskScore(0.5); // 예시 점수
                ar.setEvidenceTexts(req.getText()); 
                
                analysisRepo.save(ar); // 분석 리포트 테이블 업데이트
            }
        }
        
        sessionRepo.save(session);

        ChatBroadcast b = new ChatBroadcast();
        b.setSessionId(session.getSessionId());
        b.setSpeaker(m.getSpeaker());
        b.setText(m.getText());
        b.setCreatedAt(LocalDateTime.now().toString());
        b.setSeq(m.getSeq());
        
        return b;
    }

    public List<ChatSession> getAllSessions() {
        return sessionRepo.findAll();
    }

    public List<ChatMessage> getMessagesBySessionId(String sessionId) {
        ChatSession session = sessionRepo.findBySessionId(sessionId)
                .orElseThrow(() -> new RuntimeException("세션을 찾을 수 없습니다."));
        return messageRepo.findBySessionOrderBySeqAsc(session);
    }
}