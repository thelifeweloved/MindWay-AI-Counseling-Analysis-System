-- =====================================================
-- [최종 완성본] MindWay 데이터베이스 스키마
-- 작성일: 2026.02.14 / 작성자: 정이안
-- 과제명: 상담 이탈 신호 탐지 및 상담 품질 분석 AI 서비스
-- =====================================================
-- 특징: 
-- 1. 총 14개 테이블로 구성된 분석 중심 아키텍처
-- 2. 이탈 신호(Dropout) 분석을 위한 Window-Based 데이터 구조
-- 3. 실시간 AI 헬퍼(HyperCLOVA X) 연동 최적화 인덱스 반영
-- =====================================================

-- -----------------------------------------------------
-- 1. 상담사 테이블 (counselor)
-- 설명: 시스템을 이용하는 상담사 정보 관리. 
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS counselor (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    email      VARCHAR(50) NOT NULL COMMENT '로그인 이메일',
    pwd        VARCHAR(255) NOT NULL COMMENT '암호화된 비밀번호',
    name       VARCHAR(50) NOT NULL COMMENT '상담사 실명',
    role       ENUM('ADMIN', 'USER') NOT NULL DEFAULT 'USER' COMMENT '권한 구분',
    active     BOOLEAN NOT NULL DEFAULT TRUE COMMENT '계정 활성화 여부',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_counselor_email (email),
    CONSTRAINT ck_counselor_role CHECK (role IN ('ADMIN', 'USER'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='상담사 마스터';

-- -----------------------------------------------------
-- 2. 내담자 테이블 (client)
-- 설명: 상담을 받는 내담자 정보. status는 AI 분석에 의해 업데이트됨.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS client (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    code       VARCHAR(30) NOT NULL COMMENT '내담자 고유 코드',
    name       VARCHAR(50) NOT NULL,
    status     ENUM('안정', '주의', '개선필요') NOT NULL DEFAULT '안정' COMMENT '위험도 등급',
    phone      VARCHAR(20) NULL,
    active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_client_code (code),
    KEY ix_client_name (name),
    KEY ix_client_status_active (status, active),
    CONSTRAINT ck_client_status CHECK (status IN ('안정', '주의', '개선필요'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='내담자 마스터';

-- -----------------------------------------------------
-- 3. 주제/고민유형 정의 테이블 (topic)
-- 설명: 상담 주제 카테고리. AI가 자동으로 분류하거나 관리자가 등록함.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS topic (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    code       VARCHAR(20) NOT NULL COMMENT '주제 코드',
    name       VARCHAR(255) NOT NULL COMMENT '주제명',
    type       ENUM('REGISTER', 'AI') NOT NULL COMMENT '등록 출처',
    descr      TEXT NOT NULL COMMENT '주제 상세 설명',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_topic_code (code),
    KEY ix_topic_type (type),
    CONSTRAINT ck_topic_type CHECK (type IN ('REGISTER', 'AI'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='고민 주제 사전';

-- -----------------------------------------------------
-- 4. 상담 예약 테이블 (appt)
-- 설명: 상담 세션 시작 전의 예약 정보 관리.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS appt (
    id           BIGINT NOT NULL AUTO_INCREMENT,
    client_id    BIGINT NOT NULL,
    counselor_id BIGINT NULL,
    at           TIMESTAMP NOT NULL COMMENT '예약 시각',
    status       ENUM('REQUESTED', 'CONFIRMED', 'CANCELLED', 'COMPLETED') NOT NULL DEFAULT 'REQUESTED',
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_appt_client_time (client_id, at),
    KEY ix_appt_status (status),
    CONSTRAINT fk_appt_client FOREIGN KEY (client_id) REFERENCES client(id),
    CONSTRAINT fk_appt_counselor FOREIGN KEY (counselor_id) REFERENCES counselor(id),
    CONSTRAINT ck_appt_status CHECK (status IN ('REQUESTED', 'CONFIRMED', 'CANCELLED', 'COMPLETED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='상담 예약 일정';

-- -----------------------------------------------------
-- 5. 상담 세션 테이블 (sess)
-- 설명: 실제 진행되는 상담 단위. 이탈 분석의 기준 테이블.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS sess (
    id             BIGINT NOT NULL AUTO_INCREMENT,
    uuid           VARCHAR(50) NOT NULL COMMENT '채팅방 고유 UUID',
    counselor_id   BIGINT NOT NULL,
    client_id      BIGINT NOT NULL,
    appt_id        BIGINT NULL,
    channel        ENUM('CHAT', 'VOICE') NOT NULL DEFAULT 'CHAT' COMMENT '상담 채널',
    progress       ENUM('WAITING', 'ACTIVE', 'CLOSED') NOT NULL DEFAULT 'WAITING' COMMENT '진행 상태',
    start_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_at         TIMESTAMP NULL,
    end_reason     ENUM('NORMAL', 'DROPOUT', 'TECH', 'UNKNOWN') NULL COMMENT '이탈 여부 판별 핵심',
    sat            BOOLEAN NULL COMMENT '1=만족, 0=불만족',
    sat_note       VARCHAR(255) NULL COMMENT '만족도 한줄 피드백',
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
    CONSTRAINT ck_sess_sat CHECK (sat IS NULL OR sat IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='상담 세션';

-- -----------------------------------------------------
-- 6. 메시지 테이블 (msg)
-- 설명: 상담 중 발생하는 모든 텍스트/시스템 메시지 로그.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS msg (
    id          BIGINT NOT NULL AUTO_INCREMENT,
    sess_id     BIGINT NOT NULL,
    speaker     ENUM('COUNSELOR', 'CLIENT', 'SYSTEM') NOT NULL,
    speaker_id  BIGINT NULL,
    text        TEXT NULL,
    stt_conf    DECIMAL(3,2) NOT NULL DEFAULT 0.00 COMMENT 'STT 신뢰도(0~1)',
    at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_msg_id_sess (id, sess_id) COMMENT 'Alert 테이블 복합키 참조용',
    KEY ix_msg_sess_time (sess_id, at),
    CONSTRAINT fk_msg_sess FOREIGN KEY (sess_id) REFERENCES sess(id),
    CONSTRAINT ck_msg_stt_conf CHECK (stt_conf BETWEEN 0.00 AND 1.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='상담 메시지 로그';

-- -----------------------------------------------------
-- 7. STT 음성 구간 테이블 (stt)
-- 설명: 음성 상담 시 발화 구간별 텍스트 변환 결과 및 신뢰도.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS stt (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    sess_id    BIGINT NOT NULL,
    speaker    ENUM('COUNSELOR', 'CLIENT') NOT NULL,
    s_ms       INT UNSIGNED NOT NULL COMMENT '시작 지점(ms)',
    e_ms       INT UNSIGNED NOT NULL COMMENT '종료 지점(ms)',
    text       TEXT NOT NULL,
    conf       DECIMAL(3,2) NOT NULL DEFAULT 0.00 COMMENT 'STT 신뢰도(0~1)',
    meta       JSON NOT NULL COMMENT '모델 정보 등',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_stt_sess_time (sess_id, s_ms, e_ms),
    CONSTRAINT fk_stt_sess FOREIGN KEY (sess_id) REFERENCES sess(id),
    CONSTRAINT ck_stt_conf CHECK (conf BETWEEN 0.00 AND 1.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='STT 발화 구간 분석';

-- -----------------------------------------------------
-- 8. 표정 점수(보조) 테이블 (face)
-- 설명: 카메라 동의 시 내담자의 표정 기반 감정 수치 저장.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS face (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    sess_id    BIGINT NOT NULL,
    at         TIMESTAMP NOT NULL COMMENT '측정 시각',
    label      VARCHAR(30) NULL COMMENT '감정 라벨(안정, 불안 등)',
    score      DECIMAL(3,2) NULL COMMENT '감정 강도(0~1)',
    dist       JSON NOT NULL COMMENT '전체 감정 확률 분포',
    meta       JSON NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_face_sess_time (sess_id, at),
    CONSTRAINT fk_face_sess FOREIGN KEY (sess_id) REFERENCES sess(id),
    CONSTRAINT ck_face_score CHECK (score IS NULL OR score BETWEEN 0.00 AND 1.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='비언어 표정 분석 지표';

-- -----------------------------------------------------
-- 9. 내담자 고민유형 매핑 테이블 (client_topic)
-- 설명: 한 명의 내담자가 가진 여러 고민 주제와 우선순위 관리.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS client_topic (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    client_id  BIGINT NOT NULL,
    topic_id   BIGINT NOT NULL,
    prio       TINYINT NOT NULL DEFAULT 1 COMMENT '우선순위(1~)',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_client_topic (client_id, topic_id),
    CONSTRAINT fk_client_topic_client FOREIGN KEY (client_id) REFERENCES client(id),
    CONSTRAINT fk_client_topic_topic FOREIGN KEY (topic_id) REFERENCES topic(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='내담자별 주요 고민 매핑';

-- -----------------------------------------------------
-- 10. 이탈 신호/조치 테이블 (alert)
-- 설명: 실시간 탐지된 위험 신호. Risk Score 계산의 근거 데이터.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS alert (
    id      BIGINT NOT NULL AUTO_INCREMENT,
    sess_id BIGINT NOT NULL,
    msg_id  BIGINT NOT NULL,
    type    VARCHAR(20) NOT NULL COMMENT '위험 유형(DELAY, RISK_WORD 등)',
    status  ENUM('DETECTED', 'RESOLVED') NOT NULL DEFAULT 'DETECTED',
    score   DECIMAL(3,2) NULL COMMENT '위험도 신호 강도(0~1)',
    rule    VARCHAR(50) NULL COMMENT '적용된 탐지 규칙 코드',
    action  TEXT NULL COMMENT '상담사에게 제공된 추천 조치',
    at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_alert_sess_time (sess_id, at),
    KEY ix_alert_status (status),
    CONSTRAINT fk_alert_sess 
        FOREIGN KEY (sess_id) REFERENCES sess(id),
    CONSTRAINT fk_alert_msg_same_sess 
        FOREIGN KEY (msg_id, sess_id) REFERENCES msg(id, sess_id),
    CONSTRAINT ck_alert_status CHECK (status IN ('DETECTED', 'RESOLVED')),
    CONSTRAINT ck_alert_score CHECK (score IS NULL OR score BETWEEN 0.00 AND 1.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='실시간 위험 신호 탐지 이력';

-- -----------------------------------------------------
-- 11. 세션 품질 분석 테이블 (quality)
-- 설명: 종료된 상담의 대화 흐름 및 품질 총괄 점수.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS quality (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    sess_id    BIGINT NOT NULL,
    flow       DECIMAL(5,2) NOT NULL COMMENT '상담 흐름 점수(0~100)',
    score      DECIMAL(5,2) NOT NULL COMMENT '최종 품질 점수(0~100)',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_quality_sess (sess_id),
    CONSTRAINT fk_quality_sess FOREIGN KEY (sess_id) REFERENCES sess(id),
    CONSTRAINT ck_quality_flow CHECK (flow BETWEEN 0.00 AND 100.00),
    CONSTRAINT ck_quality_score CHECK (score BETWEEN 0.00 AND 100.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='상담 품질 종합 분석';

-- -----------------------------------------------------
-- 12. 업로드 파일 테이블 (file)
-- 설명: 상담 중 공유된 파일(과제, 이미지 등) 관리.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS file (
    id           BIGINT NOT NULL AUTO_INCREMENT,
    counselor_id BIGINT NOT NULL,
    client_id    BIGINT NOT NULL,
    sess_id      BIGINT NULL,
    name         TEXT NOT NULL COMMENT '원본파일명',
    size         INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '파일 크기(byte)',
    ext          VARCHAR(30) NOT NULL COMMENT '확장자',
    status       ENUM('UPLOADED', 'PROCESSING', 'COMPLETED', 'FAILED') NOT NULL DEFAULT 'UPLOADED',
    uploaded_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT fk_file_counselor FOREIGN KEY (counselor_id) REFERENCES counselor(id),
    CONSTRAINT fk_file_client FOREIGN KEY (client_id) REFERENCES client(id),
    CONSTRAINT fk_file_sess FOREIGN KEY (sess_id) REFERENCES sess(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='상담 관련 파일 관리';

-- -----------------------------------------------------
-- 13. 텍스트 정서 분석 테이블 (text_emotion)
-- 설명: 각 메시지별 AI 정서 분석 라벨 및 확신 점수.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS text_emotion (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    msg_id     BIGINT NOT NULL,
    label      VARCHAR(30) NOT NULL COMMENT '감정 라벨(슬픔, 기쁨 등)',
    score      DECIMAL(3,2) NOT NULL DEFAULT 0.00 COMMENT '정서 확신도(0~1)',
    meta       JSON NOT NULL COMMENT '모델 버전 등',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_text_emotion_msg_time (msg_id, created_at),
    CONSTRAINT fk_text_emotion_msg FOREIGN KEY (msg_id) REFERENCES msg(id),
    CONSTRAINT ck_text_emotion_score CHECK (score BETWEEN 0.00 AND 1.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='메시지별 감정 분석 결과';

-- -----------------------------------------------------
-- 14. 토픽별 세션 분석 요약 테이블 (sess_analysis)
-- 설명: 상담 종료 후 AI가 생성한 대화 요약 및 상담사 의견 기록.
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS sess_analysis (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    sess_id    BIGINT NOT NULL,
    topic_id   BIGINT NOT NULL,
    summary    TEXT NOT NULL COMMENT 'AI 기반 자동 상담 요약',
    note       TEXT NOT NULL COMMENT '상담사가 직접 작성한 특이사항',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_sess_topic (sess_id, topic_id),
    CONSTRAINT fk_sess_analysis_sess FOREIGN KEY (sess_id) REFERENCES sess(id),
    CONSTRAINT fk_sess_analysis_topic FOREIGN KEY (topic_id) REFERENCES topic(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='상담 세션 종합 요약 리포트';