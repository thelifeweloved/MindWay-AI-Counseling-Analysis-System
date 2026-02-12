package com.counseling.entity;

import jakarta.persistence.*;
import lombok.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "chat_sessions")
@Getter @Setter @NoArgsConstructor @AllArgsConstructor @Builder
public class ChatSession {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "session_id", unique = true, nullable = false)
    private String sessionId; // 분석 서버 연동 키

    private String clientId;
    private String mode = "BOT";
    private String status = "ACTIVE";
    private String endedReason = "UNKNOWN";

    private LocalDateTime startedAt;
    private LocalDateTime endedAt;
    private LocalDateTime lastClientMsgAt; // 내담자 지연 분석 핵심
    private LocalDateTime lastMsgAt;

    @PrePersist
    public void prePersist() { this.startedAt = LocalDateTime.now(); }
    
}