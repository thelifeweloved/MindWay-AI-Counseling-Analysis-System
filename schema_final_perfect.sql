스키마 수정이요....


-- =====================================================
-- [최종 제출용] MindWay 데이터베이스 스키마
-- 작성일: 2026.02.26 / 작성자: 정이안
-- 서비스명: 비대면 상담 분석 보조 AI 리포트 서비스
-- =====================================================

-- 공통: utf8mb4 권장
SET NAMES utf8mb4;

-- -----------------------------------------------------
-- 1. 상담사 테이블 (counselor)
-- 설명: 시스템을 이용하는 상담사 정보 관리
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS counselor (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    email      VARCHAR(50) NOT NULL COMMENT '로그인 이메일',
    pwd        VARCHAR(255) NOT NULL COMMENT '암호화된 비밀번호',
    name       VARCHAR(50) NOT NULL COMMENT '상담사 실명',
    role       ENUM('ADMIN', 'USER') NOT NULL DEFAULT 'USER' COMMENT '권한 구분',
    active     TINYINT(1) NOT NULL DEFAULT 1 COMMENT '계정 활성화 여부(1=활성, 0=비활성)',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_counselor_email (email),
    CONSTRAINT ck_counselor_role CHECK (role IN ('ADMIN', 'USER'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='상담사 마스터';

-- -----------------------------------------------------
-- 2. 내담자 테이블 (client)
-- 설명: 상담을 받는 내담자 정보. status는 운영 정책에 따라 업데이트됨
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS client (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    email      VARCHAR(50) NOT NULL COMMENT '로그인 ID',
    pwd        VARCHAR(255) NOT NULL COMMENT '비밀번호(암호화 저장)',
    code       VARCHAR(30) NOT NULL COMMENT '내담자 고유 코드',
    name       VARCHAR(50) NOT NULL,
    status     ENUM('안정', '주의', '개선필요') NOT NULL DEFAULT '안정' COMMENT '상태 등급',
    phone      VARCHAR(20) NOT NULL,
    active     TINYINT(1) NOT NULL DEFAULT 1 COMMENT '계정 활성화 여부(1=활성, 0=비활성)',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_client_code (code),
    UNIQUE KEY uk_client_email (email),
    KEY ix_client_name (name),
    KEY ix_client_status_active (status, active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='내담자 마스터';

-- -----------------------------------------------------
-- 3. 주제/고민유형 정의 테이블 (topic)
-- 설명: 상담 주제 카테고리. AI가 분류하거나 관리자가 등록함
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
-- 설명: 상담 세션 시작 전의 예약 정보 관리
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS appt (
    id           BIGINT NOT NULL AUTO_INCREMENT,
    client_id    BIGINT NOT NULL,
    counselor_id BIGINT NULL,
    at           TIMESTAMP NOT NULL COMMENT '예약 시각',
    status       ENUM('REQUESTED', 'CONFIRMED', 'CANCELLED', 'COMPLETED') NOT NULL DEFAULT 'REQUESTED' COMMENT '예약 상태',
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_appt_client_time (client_id, at),
    KEY ix_appt_status (status),
    KEY ix_appt_counselor_time (counselor_id, at),
    CONSTRAINT fk_appt_client FOREIGN KEY (client_id) REFERENCES client(id),
    CONSTRAINT fk_appt_counselor FOREIGN KEY (counselor_id) REFERENCES counselor(id),
    CONSTRAINT ck_appt_status CHECK (status IN ('REQUESTED', 'CONFIRMED', 'CANCELLED', 'COMPLETED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='예약';

-- -----------------------------------------------------
-- 5. 상담 세션 테이블 (sess)
-- 설명: 실제 진행되는 상담 단위. 리포트 생성의 기준 단위
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS sess (
    id           BIGINT NOT NULL AUTO_INCREMENT,
    uuid         VARCHAR(50) NOT NULL COMMENT '채팅방 고유 UUID',
    counselor_id BIGINT NOT NULL,
    client_id    BIGINT NOT NULL,
    appt_id      BIGINT NULL,

    channel      ENUM('CHAT') NOT NULL DEFAULT 'CHAT' COMMENT '상담 채널(텍스트 전용)',
    progress     ENUM('WAITING', 'ACTIVE', 'CLOSED') NOT NULL DEFAULT 'WAITING' COMMENT '진행 상태',

    start_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_at       TIMESTAMP NULL,

    end_reason   ENUM('NORMAL', 'DROPOUT', 'TECH', 'UNKNOWN') NULL COMMENT '종료 사유',

    sat          TINYINT(1) NULL COMMENT '만족 여부(1=만족, 0=불만족)',
    sat_note     VARCHAR(255) NULL COMMENT '만족 한 줄 피드백',

    ok_text      TINYINT(1) NOT NULL DEFAULT 1 COMMENT '텍스트 분석 동의(1=동의, 0=미동의)',
    ok_face      TINYINT(1) NOT NULL DEFAULT 0 COMMENT '표정 지표 제공 동의(1=동의, 0=미동의)',

    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uk_sess_uuid (uuid),
    KEY ix_sess_progress (progress),
    KEY ix_sess_end_reason (end_reason),

    CONSTRAINT fk_sess_counselor FOREIGN KEY (counselor_id) REFERENCES counselor(id),
    CONSTRAINT fk_sess_client FOREIGN KEY (client_id) REFERENCES client(id),
    CONSTRAINT fk_sess_appt FOREIGN KEY (appt_id) REFERENCES appt(id),

    CONSTRAINT ck_sess_sat CHECK (sat IS NULL OR sat IN (0, 1)),
    CONSTRAINT ck_sess_ok_text CHECK (ok_text IN (0, 1)),
    CONSTRAINT ck_sess_ok_face CHECK (ok_face IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='상담 세션';

-- -----------------------------------------------------
-- 6. 메시지 테이블 (msg)
-- 설명: 상담 중 발생하는 모든 텍스트/시스템 메시지 로그
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS msg (
    id          BIGINT NOT NULL AUTO_INCREMENT,
    sess_id     BIGINT NOT NULL,
    sender_type ENUM('COUNSELOR', 'CLIENT', 'SYSTEM') NOT NULL,
    sender_id   BIGINT NULL,
    text        TEXT NULL,
    file_url    TEXT NULL COMMENT '외부 저장소 파일 경로',
    at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_msg_id_sess (id, sess_id) COMMENT 'alert 복합 FK 참조용',
    KEY ix_msg_sess_time (sess_id, at),
    CONSTRAINT fk_msg_sess FOREIGN KEY (sess_id) REFERENCES sess(id),
    CONSTRAINT ck_msg_sender_type CHECK (sender_type IN ('COUNSELOR','CLIENT','SYSTEM'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='상담 메시지 로그';

-- -----------------------------------------------------
-- 7. 표정 점수(보조) 테이블 (face)
-- 설명: 동의 시 표정 기반 참고 지표(비식별 수치) 저장. 원본 영상/이미지는 저장하지 않음
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS face (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    sess_id    BIGINT NOT NULL,
    at         TIMESTAMP NOT NULL COMMENT '측정 시각',
    label      VARCHAR(30) NULL COMMENT '표정 기반 라벨(참고용)',
    score      DECIMAL(3,2) NULL COMMENT '표정 지표 점수(0~1)',
    dist       JSON NOT NULL COMMENT '표정 지표 분포(JSON)',
    meta       JSON NOT NULL COMMENT '모델/환경 메타데이터',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_face_sess_time (sess_id, at),
    CONSTRAINT fk_face_sess FOREIGN KEY (sess_id) REFERENCES sess(id),
    CONSTRAINT ck_face_score CHECK (score IS NULL OR score BETWEEN 0.00 AND 1.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='표정 기반 참고 지표';

-- -----------------------------------------------------
-- 8. 내담자 고민유형 매핑 테이블 (client_topic)
-- 설명: 내담자-주제 N:M 매핑 및 우선순위 관리
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
-- 9. 참고 신호/조치 테이블 (alert)
-- 설명: 상담 세션에서 탐지된 참고 신호 및 대응 이력 저장(판단/의사결정 자동 수행 없음)
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS alert (
    id      BIGINT NOT NULL AUTO_INCREMENT,
    sess_id BIGINT NOT NULL,
    msg_id  BIGINT NOT NULL,
    type    VARCHAR(20) NOT NULL COMMENT '신호 유형(DELAY, KEYWORD 등)',
    status  ENUM('DETECTED', 'RESOLVED') NOT NULL DEFAULT 'DETECTED',
    score   DECIMAL(3,2) NULL COMMENT '신호 강도(0~1)',
    rule    VARCHAR(50) NULL COMMENT '탐지 규칙 코드',
    action  TEXT NULL COMMENT '상담사에게 제공된 참고 조치',
    at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_alert_sess_time (sess_id, at),
    KEY ix_alert_status (status),
    CONSTRAINT fk_alert_sess FOREIGN KEY (sess_id) REFERENCES sess(id),
    CONSTRAINT fk_alert_msg_same_sess FOREIGN KEY (msg_id, sess_id) REFERENCES msg(id, sess_id),
    CONSTRAINT ck_alert_status CHECK (status IN ('DETECTED', 'RESOLVED')),
    CONSTRAINT ck_alert_score CHECK (score IS NULL OR score BETWEEN 0.00 AND 1.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='참고 신호 탐지 이력';

-- -----------------------------------------------------
-- 10. 세션 품질 분석 테이블 (quality)
-- 설명: 종료된 상담의 흐름/품질 점수(세션당 1건)
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS quality (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    sess_id    BIGINT NOT NULL,
    flow       DECIMAL(5,2) NOT NULL COMMENT '상담 흐름 점수(0~100)',
    score      DECIMAL(5,2) NOT NULL COMMENT '세션 종합 품질 점수(0~100)',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_quality_sess (sess_id),
    CONSTRAINT fk_quality_sess FOREIGN KEY (sess_id) REFERENCES sess(id),
    CONSTRAINT ck_quality_flow CHECK (flow BETWEEN 0.00 AND 100.00),
    CONSTRAINT ck_quality_score CHECK (score BETWEEN 0.00 AND 100.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='상담 품질 종합 분석';

-- -----------------------------------------------------
-- 11. 텍스트 정서 분석 테이블 (text_emotion)
-- 설명: 메시지 단위 정서 라벨/점수 저장(모델 메타 포함)
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS text_emotion (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    msg_id     BIGINT NOT NULL,
    label      VARCHAR(30) NOT NULL COMMENT '정서 라벨',
    score      DECIMAL(3,2) NOT NULL DEFAULT 0.00 COMMENT '정서 점수(0~1)',
    meta       JSON NOT NULL COMMENT '모델 버전 등',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_text_emotion_msg_time (msg_id, created_at),
    CONSTRAINT fk_text_emotion_msg FOREIGN KEY (msg_id) REFERENCES msg(id),
    CONSTRAINT ck_text_emotion_score CHECK (score BETWEEN 0.00 AND 1.00)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='메시지별 정서 분석 결과';

-- -----------------------------------------------------
-- 12. 토픽별 세션 분석 요약 테이블 (sess_analysis)
-- 설명: 세션 종료 후 요약(summary)과 상담사 의견(음표)을 토픽별로 저장
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS sess_analysis (
    id         BIGINT NOT NULL AUTO_INCREMENT,
    sess_id    BIGINT NOT NULL,
    topic_id   BIGINT NOT NULL,
    summary    TEXT NOT NULL COMMENT 'AI 기반 자동 요약',
    note       TEXT NOT NULL COMMENT '상담사 의견(필수)',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_sess_topic (sess_id, topic_id),
    CONSTRAINT fk_sess_analysis_sess FOREIGN KEY (sess_id) REFERENCES sess(id),
    CONSTRAINT fk_sess_analysis_topic FOREIGN KEY (topic_id) REFERENCES topic(id)
    -- 상담사 메모를 공백까지 막고 싶으면 아래 CHECK를 추가(선택)
    -- ,CONSTRAINT ck_sess_analysis_note_nonempty CHECK (CHAR_LENGTH(TRIM(음표)) >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='세션 요약 및 상담사 의견';