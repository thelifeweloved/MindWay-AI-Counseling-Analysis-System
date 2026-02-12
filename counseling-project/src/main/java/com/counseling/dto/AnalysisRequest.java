package com.counseling.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
public class AnalysisRequest {
    private String sessionId;
    private String text;
    private String speaker;
}