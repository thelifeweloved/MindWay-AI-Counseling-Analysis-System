package com.counseling.repository;

import com.counseling.entity.ChatSession;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;

public interface ChatSessionRepository extends JpaRepository<ChatSession, Long> {
    Optional<ChatSession> findBySessionId(String sessionId); 
}