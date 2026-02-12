package com.counseling.entity;

import jakarta.persistence.*;
import lombok.*;

@Entity
@Table(name = "analysis_results")
@Getter @Setter @Builder
@NoArgsConstructor @AllArgsConstructor
public class AnalysisResult {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @OneToOne
    @JoinColumn(name = "session_fk")
    private ChatSession session; // 대상 상담 세션

    private String riskLevel;    // 위험도 (High, Mid, Low)
    private Double riskScore;    // 위험 점수
    private Integer topicId;     // 대화 주제 ID
    private Double topicProb;    // 주제 일치 확률
    
    @Column(columnDefinition = "TEXT")
    private String signalsJson;  // 감지된 신호들 (JSON 형태)
    
    @Column(columnDefinition = "TEXT")
    private String evidenceTexts; // 분석 근거 문장들
}