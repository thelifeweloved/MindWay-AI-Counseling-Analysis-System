package com.counseling.controller;

import com.counseling.entity.ChatMessage;
import com.counseling.entity.ChatSession;
import com.counseling.service.ChatService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/sessions")
@RequiredArgsConstructor
public class ChatSessionController {

    private final ChatService chatService;

    // 1. 모든 상담 목록 조회 (대시보드용)
    @GetMapping
    public List<ChatSession> getAllSessions() {
        return chatService.getAllSessions();
    }

    // 2. 특정 상담의 전체 메시지 조회 (상세 보기용)
    @GetMapping("/{sessionId}/messages")
    public List<ChatMessage> getMessages(@PathVariable String sessionId) {
        return chatService.getMessagesBySessionId(sessionId);
    }
}