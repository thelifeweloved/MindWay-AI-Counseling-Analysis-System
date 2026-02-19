-- MindWay 최종 명세서(2026.02.14) 기준 통합 시드 데이터
USE campus_25IS_DCX1_p3_2;

-- 0) 기존 데이터 초기화 (FK 제약 무시)
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE alert; TRUNCATE TABLE quality; TRUNCATE TABLE sess_analysis;
TRUNCATE TABLE text_emotion; TRUNCATE TABLE client_topic; TRUNCATE TABLE msg;
TRUNCATE TABLE sess; TRUNCATE TABLE appt; TRUNCATE TABLE topic;
TRUNCATE TABLE client; TRUNCATE TABLE counselor;
SET FOREIGN_KEY_CHECKS = 1;

-- 1) counselor (상담사 마스터)
INSERT INTO counselor (id, email, pwd, name, role, active)
VALUES (1, 'c1@mindway.com', 'pwd123', '김도움', 'USER', TRUE);

-- 2) client (내담자 마스터: '안정', '주의', '개선필요')
INSERT INTO client (id, code, name, status, phone, active)
VALUES (1, 'CL001', '이내담', '주의', '010-1234-5678', TRUE);

-- 3) topic (상담 주제 사전)
INSERT INTO topic (id, code, name, type, descr)
VALUES (1, 'T001', '진로상담', 'REGISTER', '진로 및 적성 관련 고민');

-- 4) appt (예약 리스트)
INSERT INTO appt (id, client_id, counselor_id, at, status)
VALUES (1, 1, 1, NOW(), 'COMPLETED');

-- 5) sess (상담 세션: 이탈 시나리오 구성)
INSERT INTO sess (id, uuid, counselor_id, client_id, appt_id, channel, progress, start_at, end_at, end_reason, sat, ok_text)
VALUES (1, 'SESS-001', 1, 1, 1, 'CHAT', 'CLOSED', NOW(), NOW(), 'DROPOUT', 0, TRUE);

-- 6) msg (이탈 직전 발화 로그)
INSERT INTO msg (id, sess_id, speaker, speaker_id, text, at)
VALUES 
(1, 1, 'COUNSELOR', 1, '오늘 기분은 좀 어떠신가요?', NOW()),
(2, 1, 'CLIENT', 1, '그냥 다 그만하고 싶어요. 의미가 없네요.', NOW());

-- 7) text_emotion (정서 분석 데이터: 차트 시각화용)
INSERT INTO text_emotion (id, msg_id, label, score, meta)
VALUES 
(1, 1, '안정', 0.80, '{"model": "HCX-DASH-002"}'),
(2, 2, '슬픔/절망', 0.95, '{"model": "HCX-DASH-002"}');

-- 8) alert (위험 신호 탐지: 리스크 스코어 반영)
INSERT INTO alert (id, sess_id, msg_id, type, status, score, rule, action)
VALUES (1, 1, 2, 'RISK_WORD', 'DETECTED', 0.95, 'NEG_KEYWORD_ENGINE', '긴급 공감 및 안전 확인 개입 권장');

-- 9) quality (종합 품질 분석)
INSERT INTO quality (id, sess_id, flow, score)
VALUES (1, 1, 45.50, 50.00);