USE mindway;

SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE alert; TRUNCATE TABLE quality; TRUNCATE TABLE sess_analysis;
TRUNCATE TABLE text_emotion; TRUNCATE TABLE client_topic; TRUNCATE TABLE msg;
TRUNCATE TABLE sess; TRUNCATE TABLE appt; TRUNCATE TABLE topic;
TRUNCATE TABLE client; TRUNCATE TABLE counselor;
SET FOREIGN_KEY_CHECKS = 1;

-- 1) counselor
INSERT INTO counselor (id, email, pwd, name, role)
VALUES (1, 'c1@mindway.com', 'pwd123', '김도움', 'USER');

-- 2) client (주의: 명세서상 ENUM 값인 '안정', '주의', '개선필요'만 허용) 
INSERT INTO client (id, code, name, status, phone)
VALUES (1, 'CL001', '이내담', '주의', '010-1234-5678');

-- 3) topic
INSERT INTO topic (id, code, name, type, descr)
VALUES (1, 'T001', '진로상담', 'REGISTER', '진로 관련 고민');

-- 4) appt (status: REQUESTED, CONFIRMED, CANCELLED, COMPLETED) [cite: 43, 55]
INSERT INTO appt (id, client_id, counselor_id, at, status)
VALUES (1, 1, 1, NOW(), 'COMPLETED');

-- 5) sess (progress: WAITING, ACTIVE, CLOSED / channel: CHAT, VOICE) [cite: 60, 80, 81]
INSERT INTO sess (id, uuid, counselor_id, client_id, appt_id, channel, progress, start_at, end_reason, ok_text)
VALUES (1, 'SESS-001', 1, 1, 1, 'CHAT', 'CLOSED', NOW(), 'DROPOUT', TRUE);

-- 6) msg (speaker: COUNSELOR, CLIENT, SYSTEM) [cite: 125, 134]
INSERT INTO msg (id, sess_id, speaker, speaker_id, text, at)
VALUES (1, 1, 'CLIENT', 1, '상담 그만하고 싶어요.', NOW());

-- 7) alert (status: DETECTED, RESOLVED) [cite: 259, 271]
INSERT INTO alert (id, sess_id, msg_id, type, status, score, rule)
VALUES (1, 1, 1, 'RISK_WORD', 'DETECTED', 0.95, 'EMO_NEG_0.8');