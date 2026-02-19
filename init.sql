/* =========================================================
   MindWay 최종 통합 초기화 스크립트 (init.sql)
   - 최종 명세서(2026.02.14) 규격 100% 준수
   - 공용 DB 서버 환경 최적화
========================================================= */

SET NAMES utf8mb4;
SET time_zone = '+09:00';

-- 0. 공용 데이터베이스 선택
CREATE DATABASE IF NOT EXISTS campus_25IS_DCX1_p3_2;
USE campus_25IS_DCX1_p3_2;

-- 1. counselor (상담사)
CREATE TABLE IF NOT EXISTS counselor (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    email      VARCHAR(50) NOT NULL,
    pwd        VARCHAR(255) NOT NULL,
    name       VARCHAR(50) NOT NULL,
    role       ENUM('ADMIN', 'USER') NOT NULL DEFAULT 'USER',
    active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_counselor_email (email),
    CONSTRAINT ck_counselor_role CHECK (role IN ('ADMIN', 'USER'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='상담사';

-- 2. client (내담자)
CREATE TABLE IF NOT EXISTS client (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    code       VARCHAR(30) NOT NULL,
    name       VARCHAR(50) NOT NULL,
    status     ENUM('안정', '주의', '개선필요') NOT NULL DEFAULT '안정',
    phone      VARCHAR(20) NULL,
    active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_client_code (code),
    KEY ix_client_name (name),
    KEY ix_client_status_active (status, active),
    CONSTRAINT ck_client_status CHECK (status IN ('안정', '주의', '개선필요'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='내담자';

-- 3. topic (주제)
CREATE TABLE IF NOT EXISTS topic (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    code       VARCHAR(20) NOT NULL,
    name       VARCHAR(255) NOT NULL,
    type       ENUM('REGISTER', 'AI') NOT NULL,
    descr      TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_topic_code (code),
    KEY ix_topic_name (name),
    KEY ix_topic_type (type),
    CONSTRAINT ck_topic_type CHECK (type IN ('REGISTER', 'AI'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='주제';

-- 4. appt (예약)
CREATE TABLE IF NOT EXISTS appt (
    id           BIGINT NOT NULL AUTO_INCREMENT,
    client_id    BIGINT NOT NULL,
    counselor_id BIGINT NULL,
    at           TIMESTAMP NOT NULL,
    status       ENUM('REQUESTED', 'CONFIRMED', 'CANCELLED', 'COMPLETED') NOT NULL DEFAULT 'REQUESTED',
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_appt_client_time (client_id, at),
    KEY ix_appt_status (status),
    CONSTRAINT fk_appt_client FOREIGN KEY (client_id) REFERENCES client(id),
    CONSTRAINT fk_appt_counselor FOREIGN KEY (counselor_id) REFERENCES counselor(id),
    CONSTRAINT ck_appt_status CHECK (status IN ('REQUESTED', 'CONFIRMED', 'CANCELLED', 'COMPLETED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='예약';

-- 5. sess (세션: 우리의 약속 필드 포함)
CREATE TABLE IF NOT EXISTS sess (
    id             BIGINT NOT NULL AUTO_INCREMENT,
    uuid           VARCHAR(50) NOT NULL,
    counselor_id   BIGINT NOT NULL,
    client_id      BIGINT NOT NULL,
    appt_id        BIGINT NULL,
    channel        ENUM('CHAT', 'VOICE') NOT NULL DEFAULT 'CHAT',
    progress       ENUM('WAITING', 'ACTIVE', 'CLOSED') NOT NULL DEFAULT 'WAITING',
    start_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_at         TIMESTAMP NULL,
    end_reason     ENUM('NORMAL', 'DROPOUT', 'TECH', 'UNKNOWN') NULL,
    sat            BOOLEAN NULL COMMENT '1=만족, 0=불만족',
    sat_note       VARCHAR(255) NULL,
    ok_text        BOOLEAN NOT NULL DEFAULT TRUE,
    ok_voice       BOOLEAN NOT NULL DEFAULT FALSE,
    ok_face        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_sess_uuid (uuid),
    KEY ix_sess_progress (progress),
    KEY ix_sess_end_reason (end_reason),
    CONSTRAINT fk_sess_counselor FOREIGN KEY (counselor_id) REFERENCES counselor(id),
    CONSTRAINT fk_sess_client FOREIGN KEY (client_id) REFERENCES client(id),
    CONSTRAINT fk_sess_appt FOREIGN KEY (appt_id) REFERENCES appt(id),
    CONSTRAINT ck_sess_channel CHECK (channel IN ('CHAT', 'VOICE')),
    CONSTRAINT ck_sess_progress CHECK (progress IN ('WAITING', 'ACTIVE', 'CLOSED')),
    CONSTRAINT ck_sess_end_reason CHECK (end_reason IS NULL OR end_reason IN ('NORMAL', 'DROPOUT', 'TECH', 'UNKNOWN')),
    CONSTRAINT ck_sess_sat CHECK (sat IS NULL OR sat IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='상담 세션';

-- 6. msg (메시지)
CREATE TABLE IF NOT EXISTS msg (
    id          BIGINT NOT NULL AUTO_INCREMENT,
    sess_id     BIGINT NOT NULL,
    speaker     ENUM('COUNSELOR', 'CLIENT', 'SYSTEM') NOT NULL,
    speaker_id  BIGINT NULL,
    text        TEXT NULL,
    stt_conf    DECIMAL(3,2) NOT NULL DEFAULT 0.00,
    at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_msg_id_sess (id, sess_id),
    KEY ix_msg_sess_time (sess_id, at),
    CONSTRAINT fk_msg_sess FOREIGN KEY (sess_id) REFERENCES sess(id),
    CONSTRAINT ck_msg_speaker CHECK (speaker IN ('COUNSELOR', 'CLIENT', 'SYSTEM')),
    CONSTRAINT ck_msg_stt_conf CHECK (stt_conf BETWEEN 0.00 AND 1.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='메시지';

-- 7. stt (음성 구간)
CREATE TABLE IF NOT EXISTS stt (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    sess_id    BIGINT NOT NULL,
    speaker    ENUM('COUNSELOR', 'CLIENT') NOT NULL,
    s_ms       INT UNSIGNED NOT NULL,
    e_ms       INT UNSIGNED NOT NULL,
    text       TEXT NOT NULL,
    conf       DECIMAL(3,2) NOT NULL DEFAULT 0.00,
    meta       JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_stt_sess_time (sess_id, s_ms, e_ms),
    CONSTRAINT fk_stt_sess FOREIGN KEY (sess_id) REFERENCES sess(id),
    CONSTRAINT ck_stt_speaker CHECK (speaker IN ('COUNSELOR', 'CLIENT')),
    CONSTRAINT ck_stt_conf CHECK (conf BETWEEN 0.00 AND 1.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='STT';

-- 8. face (표정 분석)
CREATE TABLE IF NOT EXISTS face (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    sess_id    BIGINT NOT NULL,
    at         TIMESTAMP NOT NULL,
    label      VARCHAR(30) NULL,
    score      DECIMAL(3,2) NULL,
    dist       JSON NOT NULL,
    meta       JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_face_sess_time (sess_id, at),
    CONSTRAINT fk_face_sess FOREIGN KEY (sess_id) REFERENCES sess(id),
    CONSTRAINT ck_face_score CHECK (score IS NULL OR score BETWEEN 0.00 AND 1.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='표정 점수';

-- 9. client_topic (매핑)
CREATE TABLE IF NOT EXISTS client_topic (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    client_id  BIGINT NOT NULL,
    topic_id   BIGINT NOT NULL,
    prio       TINYINT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_client_topic (client_id, topic_id),
    CONSTRAINT fk_client_topic_client FOREIGN KEY (client_id) REFERENCES client(id),
    CONSTRAINT fk_client_topic_topic FOREIGN KEY (topic_id) REFERENCES topic(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='내담자 고민유형';

-- 10. alert (이탈 신호)
CREATE TABLE IF NOT EXISTS alert (
    id      BIGINT NOT NULL AUTO_INCREMENT,
    sess_id BIGINT NOT NULL,
    msg_id  BIGINT NOT NULL,
    type    VARCHAR(20) NOT NULL,
    status  ENUM('DETECTED', 'RESOLVED') NOT NULL DEFAULT 'DETECTED',
    score   DECIMAL(3,2) NULL,
    rule    VARCHAR(50) NULL,
    action  TEXT NULL,
    at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_alert_sess_time (sess_id, at),
    CONSTRAINT fk_alert_sess FOREIGN KEY (sess_id) REFERENCES sess(id),
    CONSTRAINT fk_alert_msg_same_sess FOREIGN KEY (msg_id, sess_id) REFERENCES msg(id, sess_id),
    CONSTRAINT ck_alert_status CHECK (status IN ('DETECTED', 'RESOLVED')),
    CONSTRAINT ck_alert_score CHECK (score IS NULL OR score BETWEEN 0.00 AND 1.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='이탈 신호';

-- 11. quality (품질 점수)
CREATE TABLE IF NOT EXISTS quality (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    sess_id    BIGINT NOT NULL,
    flow       DECIMAL(5,2) NOT NULL,
    score      DECIMAL(5,2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_quality_sess (sess_id),
    CONSTRAINT fk_quality_sess FOREIGN KEY (sess_id) REFERENCES sess(id),
    CONSTRAINT ck_quality_flow CHECK (flow BETWEEN 0.00 AND 100.00),
    CONSTRAINT ck_quality_score CHECK (score BETWEEN 0.00 AND 100.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='품질 분석';

-- 12. file (업로드 파일)
CREATE TABLE IF NOT EXISTS file (
    id           BIGINT NOT NULL AUTO_INCREMENT,
    counselor_id BIGINT NOT NULL,
    client_id    BIGINT NOT NULL,
    sess_id      BIGINT NULL,
    name         TEXT NOT NULL,
    size         INT UNSIGNED NOT NULL DEFAULT 0,
    ext          VARCHAR(30) NOT NULL,
    status       ENUM('UPLOADED', 'PROCESSING', 'COMPLETED', 'FAILED') NOT NULL DEFAULT 'UPLOADED',
    uploaded_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_file_sess (sess_id),
    CONSTRAINT fk_file_counselor FOREIGN KEY (counselor_id) REFERENCES counselor(id),
    CONSTRAINT fk_file_client FOREIGN KEY (client_id) REFERENCES client(id),
    CONSTRAINT fk_file_sess FOREIGN KEY (sess_id) REFERENCES sess(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='업로드 파일';

-- 13. text_emotion (정서 분석)
CREATE TABLE IF NOT EXISTS text_emotion (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    msg_id     BIGINT NOT NULL,
    label      VARCHAR(30) NOT NULL,
    score      DECIMAL(3,2) NOT NULL DEFAULT 0.00,
    meta       JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_text_emotion_msg_time (msg_id, created_at),
    CONSTRAINT fk_text_emotion_msg FOREIGN KEY (msg_id) REFERENCES msg(id),
    CONSTRAINT ck_text_emotion_score CHECK (score BETWEEN 0.00 AND 1.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='텍스트 정서 분석';

-- 14. sess_analysis (요약)
CREATE TABLE IF NOT EXISTS sess_analysis (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    sess_id    BIGINT NOT NULL,
    topic_id   BIGINT NOT NULL,
    summary    TEXT NOT NULL,
    note       TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_sess_topic (sess_id, topic_id),
    CONSTRAINT fk_sess_analysis_sess FOREIGN KEY (sess_id) REFERENCES sess(id),
    CONSTRAINT fk_sess_analysis_topic FOREIGN KEY (topic_id) REFERENCES topic(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='세션 요약 리포트';