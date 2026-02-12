package com.counseling.dto;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class ChatBroadcast {
    private String sessionId;
    private String speaker;
    private String text;
    private String createdAt;
    private int seq; 
}