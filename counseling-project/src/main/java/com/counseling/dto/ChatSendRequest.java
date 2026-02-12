package com.counseling.dto;

import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class ChatSendRequest {
    private String sessionId; 
    private String speaker;   
    private String text;      
}