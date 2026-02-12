package com.counseling.controller;

import com.counseling.dto.*;
import com.counseling.service.ChatService;
import lombok.RequiredArgsConstructor;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Controller;

@Controller
@RequiredArgsConstructor
public class ChatWsController {
    private final SimpMessagingTemplate messagingTemplate;
    private final ChatService chatService;

    @MessageMapping("/chat/send")
    public void onMessage(ChatSendRequest req) {
        ChatBroadcast saved = chatService.saveAndBuildBroadcast(req);
        messagingTemplate.convertAndSend("/topic/chat/" + saved.getSessionId(), saved); // [cite: 200]
    }
}