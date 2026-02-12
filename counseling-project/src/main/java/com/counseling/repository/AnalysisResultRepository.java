package com.counseling.repository;

import com.counseling.entity.AnalysisResult;
import com.counseling.entity.ChatSession;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;

public interface AnalysisResultRepository extends JpaRepository<AnalysisResult, Long> {
    Optional<AnalysisResult> findBySession(ChatSession session); // 세션으로 분석 결과 찾기
}