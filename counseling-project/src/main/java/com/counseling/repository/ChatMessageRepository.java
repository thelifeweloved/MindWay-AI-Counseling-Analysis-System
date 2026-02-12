package com.counseling.repository;

import com.counseling.entity.ChatMessage;
import com.counseling.entity.ChatSession;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;

public interface ChatMessageRepository extends JpaRepository<ChatMessage, Long> {
    List<ChatMessage> findBySessionOrderBySeqAsc(ChatSession session); 
}