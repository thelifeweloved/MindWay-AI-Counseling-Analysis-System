USE mindway;

-- FK 때문에 삭제/삽입 순서 중요
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

-- 1) counselor
INSERT INTO counselor (id, email, pwd, name, role, active)
VALUES (1, 'c1@example.com', 'x', 'c1', 'USER', TRUE);

-- 2) client
-- ck_client_status: ('안정','주의','개선필요') 중 하나만 가능
INSERT INTO client (id, code, name, status, phone, active)
VALUES (1, 'CL001', 'u1', '주의', NULL, TRUE);

-- 3) topic
-- ck_topic_type: ('REGISTER','AI') 중 하나만 가능
INSERT INTO topic (id, code, name, type, descr)
VALUES
(1, 'T1', 'career',  'REGISTER', 'reg topic'),
(2, 'T2', 'anxiety', 'AI',       'ai topic');

-- 4) appt
INSERT INTO appt (id, client_id, counselor_id, at, status)
VALUES (1, 1, 1, NOW(), 'CONFIRMED');

-- 5) sess
-- ck_sess_channel: ('CHAT','VOICE') 중 하나만 가능
INSERT INTO sess (
  id, uuid, counselor_id, client_id, appt_id,
  channel, progress, start_at, end_at, end_reason,
  sat, sat_note, ok_text, ok_voice, ok_face, created_at
)
VALUES (
  1, 'S-UUID-0001', 1, 1, 1,
  'CHAT', 'IN_PROGRESS', NOW(), NULL, NULL,
  NULL, NULL, TRUE, FALSE, FALSE, NOW()
);

-- 6) msg
-- ck_msg_speaker: ('COUNSELOR','CLIENT','SYSTEM') 중 하나만 가능
INSERT INTO msg (id, sess_id, speaker, speaker_id, text, emoji, file_url, stt_conf, at)
VALUES
(1, 1, 'CLIENT',    1, 'tired',         NULL, NULL, 0.0, NOW()),
(2, 1, 'COUNSELOR', 1, 'tell me more',  NULL, NULL, 0.0, NOW());

-- 7) quality
-- quality.sess_id 는 UNIQUE라 세션당 1개만 가능
INSERT INTO quality (id, sess_id, flow, score, created_at)
VALUES (1, 1, 2.0, 3.5, NOW());

-- (선택) alert까지 최소 1개 넣고 싶으면 아래 주석 해제
-- ck_alert_type: ('DELAY','SHORT','NEG_SPIKE','RISK_WORD')
-- INSERT INTO alert (id, sess_id, msg_id, type, status, score, rule, action, at)
-- VALUES (1, 1, 1, 'RISK_WORD', 'OPEN', 0.70, 'DEMO', 'WATCH', NOW());
