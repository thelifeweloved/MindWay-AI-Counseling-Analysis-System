-- MindWay 최종 명세서(2026.02.14) 기준 시드 데이터
USE campus_25IS_DCX1_p3_2; -- 배정받은 DB명으로 수정

-- FK 제약 임시 해제 후 초기화
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE alert;
TRUNCATE TABLE quality;
TRUNCATE TABLE text_emotion;
TRUNCATE TABLE msg;
TRUNCATE TABLE sess;
TRUNCATE TABLE appt;
TRUNCATE TABLE client_topic;
TRUNCATE TABLE topic;
TRUNCATE TABLE client;
TRUNCATE TABLE counselor;
SET FOREIGN_KEY_CHECKS = 1;

-- 1) counselor (상담사)
INSERT INTO counselor (id, email, pwd, name, role, active)
VALUES (1, 'c1@example.com', 'hashed_pwd_here', '이안상담사', 'USER', TRUE);

-- 2) client (내담자)
-- status: '안정', '주의', '개선필요'
INSERT INTO client (id, code, name, status, phone, active)
VALUES (1, 'CL001', '내담자A', '주의', '010-1234-5678', TRUE);

-- 3) topic (주제)
-- type: 'REGISTER', 'AI'
INSERT INTO topic (id, code, name, type, descr)
VALUES
(1, 'T1', '진로상담', 'REGISTER', '경로 및 직업 고민'),
(2, 'T2', '불안장애', 'AI', 'AI가 탐지한 불안 증세');

-- 4) appt (예약)
-- status: 'REQUESTED', 'CONFIRMED', 'CANCELLED', 'COMPLETED'
INSERT INTO appt (id, client_id, counselor_id, at, status)
VALUES (1, 1, 1, NOW(), 'CONFIRMED');

-- 5) sess (상담 세션)
-- progress: 'WAITING', 'ACTIVE', 'CLOSED'
-- sat: 1(만족), 0(불만족)
INSERT INTO sess (
  id, uuid, counselor_id, client_id, appt_id,
  channel, progress, start_at, end_at, end_reason,
  sat, sat_note, ok_text, ok_voice, ok_face, created_at
)
VALUES (
  1, 'S-UUID-0001', 1, 1, 1,
  'CHAT', 'ACTIVE', NOW(), NULL, NULL,
  NULL, NULL, TRUE, FALSE, FALSE, NOW()
);

-- 6) msg (메시지)
-- speaker: 'COUNSELOR', 'CLIENT', 'SYSTEM'
INSERT INTO msg (id, sess_id, speaker, speaker_id, text, stt_conf, at)
VALUES
(1, 1, 'CLIENT', 1, '요즘 너무 무기력하고 힘들어요.', 1.0, NOW()),
(2, 1, 'COUNSELOR', 1, '그런 마음이 드시는군요. 구체적으로 어떤 상황에서 더 힘드신가요?', 1.0, NOW());

-- 7) alert (이탈 신호)
-- status: 'DETECTED', 'RESOLVED'
-- score: 0.00 ~ 1.00
INSERT INTO alert (id, sess_id, msg_id, type, status, score, rule, action, at)
VALUES (1, 1, 1, 'RISK_WORD', 'DETECTED', 0.85, 'NEG_KEYWORD_ENGINE', '공감 및 안전 확인 질문 권장', NOW());

-- 8) quality (품질 분석)
-- flow, score: 0.00 ~ 100.00
INSERT INTO quality (id, sess_id, flow, score, created_at)
VALUES (1, 1, 80.00, 85.50, NOW());