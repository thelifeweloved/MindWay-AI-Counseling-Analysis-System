-- MySQL dump 10.13  Distrib 8.0.45, for Linux (x86_64)
--
-- Host: localhost    Database: mindway
-- ------------------------------------------------------
-- Server version	8.0.45

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `alert`
--

DROP TABLE IF EXISTS `alert`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alert` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `sess_id` bigint NOT NULL,
  `msg_id` bigint NOT NULL,
  `type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `score` decimal(5,4) DEFAULT NULL,
  `rule` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `action` text COLLATE utf8mb4_unicode_ci,
  `at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_alert_sess_time` (`sess_id`,`at`),
  KEY `ix_alert_type_status` (`type`,`status`),
  KEY `fk_alert_msg_same_sess` (`msg_id`,`sess_id`),
  CONSTRAINT `fk_alert_msg_same_sess` FOREIGN KEY (`msg_id`, `sess_id`) REFERENCES `msg` (`id`, `sess_id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_alert_sess` FOREIGN KEY (`sess_id`) REFERENCES `sess` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_alert_type` CHECK ((`type` in (_utf8mb4'DELAY',_utf8mb4'SHORT',_utf8mb4'NEG_SPIKE',_utf8mb4'RISK_WORD')))
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='alert';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `alert`
--

LOCK TABLES `alert` WRITE;
/*!40000 ALTER TABLE `alert` DISABLE KEYS */;
INSERT INTO `alert` VALUES (1,1,7,'RISK_WORD','OPEN',0.5000,'NEG_KEYWORD','WATCH','2026-02-13 02:04:07');
/*!40000 ALTER TABLE `alert` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `appt`
--

DROP TABLE IF EXISTS `appt`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `appt` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `client_id` bigint NOT NULL,
  `counselor_id` bigint DEFAULT NULL,
  `at` timestamp NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'REQUESTED',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_appt_client_time` (`client_id`,`at`),
  KEY `ix_appt_counselor_time` (`counselor_id`,`at`),
  KEY `ix_appt_status` (`status`),
  CONSTRAINT `fk_appt_client` FOREIGN KEY (`client_id`) REFERENCES `client` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_appt_counselor` FOREIGN KEY (`counselor_id`) REFERENCES `counselor` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='appt';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `appt`
--

LOCK TABLES `appt` WRITE;
/*!40000 ALTER TABLE `appt` DISABLE KEYS */;
INSERT INTO `appt` VALUES (1,1,1,'2026-02-13 01:33:32','CONFIRMED','2026-02-13 01:33:32');
/*!40000 ALTER TABLE `appt` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `client`
--

DROP TABLE IF EXISTS `client`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `client` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `code` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `phone` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_client_code` (`code`),
  KEY `ix_client_name` (`name`),
  CONSTRAINT `ck_client_status` CHECK ((`status` in (_utf8mb4'안정',_utf8mb4'주의',_utf8mb4'개선필요')))
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='client';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `client`
--

LOCK TABLES `client` WRITE;
/*!40000 ALTER TABLE `client` DISABLE KEYS */;
INSERT INTO `client` VALUES (1,'CL001','u1','주의',NULL,1,'2026-02-13 01:33:32');
/*!40000 ALTER TABLE `client` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `client_topic`
--

DROP TABLE IF EXISTS `client_topic`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `client_topic` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `client_id` bigint NOT NULL,
  `topic_id` bigint NOT NULL,
  `prio` tinyint NOT NULL DEFAULT '1',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_client_topic` (`client_id`,`topic_id`),
  KEY `ix_client_topic_prio` (`client_id`,`prio`),
  KEY `fk_client_topic_topic` (`topic_id`),
  CONSTRAINT `fk_client_topic_client` FOREIGN KEY (`client_id`) REFERENCES `client` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_client_topic_topic` FOREIGN KEY (`topic_id`) REFERENCES `topic` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='client_topic';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `client_topic`
--

LOCK TABLES `client_topic` WRITE;
/*!40000 ALTER TABLE `client_topic` DISABLE KEYS */;
/*!40000 ALTER TABLE `client_topic` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `counselor`
--

DROP TABLE IF EXISTS `counselor`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `counselor` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `email` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `pwd` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `role` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'USER',
  `active` tinyint(1) NOT NULL DEFAULT '1',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_counselor_email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='counselor';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `counselor`
--

LOCK TABLES `counselor` WRITE;
/*!40000 ALTER TABLE `counselor` DISABLE KEYS */;
INSERT INTO `counselor` VALUES (1,'c1@example.com','x','c1','USER',1,'2026-02-13 01:33:32');
/*!40000 ALTER TABLE `counselor` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `face`
--

DROP TABLE IF EXISTS `face`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `face` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `sess_id` bigint NOT NULL,
  `at` timestamp NOT NULL,
  `label` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `score` decimal(5,4) DEFAULT NULL,
  `dist` json NOT NULL,
  `meta` json NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_face_sess_time` (`sess_id`,`at`),
  CONSTRAINT `fk_face_sess` FOREIGN KEY (`sess_id`) REFERENCES `sess` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='face';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `face`
--

LOCK TABLES `face` WRITE;
/*!40000 ALTER TABLE `face` DISABLE KEYS */;
/*!40000 ALTER TABLE `face` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `file`
--

DROP TABLE IF EXISTS `file`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `file` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `counselor_id` bigint NOT NULL,
  `client_id` bigint NOT NULL,
  `sess_id` bigint DEFAULT NULL,
  `name` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `size` int unsigned NOT NULL DEFAULT '0',
  `ext` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'UPLOADED',
  `uploaded_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `deleted_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_file_sess` (`sess_id`),
  KEY `ix_file_client_time` (`client_id`,`uploaded_at`),
  KEY `ix_file_counselor_time` (`counselor_id`,`uploaded_at`),
  CONSTRAINT `fk_file_client` FOREIGN KEY (`client_id`) REFERENCES `client` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_file_counselor` FOREIGN KEY (`counselor_id`) REFERENCES `counselor` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_file_sess` FOREIGN KEY (`sess_id`) REFERENCES `sess` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='file';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `file`
--

LOCK TABLES `file` WRITE;
/*!40000 ALTER TABLE `file` DISABLE KEYS */;
/*!40000 ALTER TABLE `file` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `msg`
--

DROP TABLE IF EXISTS `msg`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `msg` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `sess_id` bigint NOT NULL,
  `speaker` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `speaker_id` bigint DEFAULT NULL,
  `text` text COLLATE utf8mb4_unicode_ci,
  `emoji` text COLLATE utf8mb4_unicode_ci,
  `file_url` text COLLATE utf8mb4_unicode_ci,
  `stt_conf` decimal(5,4) NOT NULL DEFAULT '0.0000',
  `at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_msg_id_sess` (`id`,`sess_id`),
  KEY `ix_msg_sess_time` (`sess_id`,`at`),
  KEY `ix_msg_speaker` (`speaker`,`speaker_id`),
  CONSTRAINT `fk_msg_sess` FOREIGN KEY (`sess_id`) REFERENCES `sess` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_msg_speaker` CHECK ((`speaker` in (_utf8mb4'COUNSELOR',_utf8mb4'CLIENT',_utf8mb4'SYSTEM')))
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='msg';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `msg`
--

LOCK TABLES `msg` WRITE;
/*!40000 ALTER TABLE `msg` DISABLE KEYS */;
INSERT INTO `msg` VALUES (1,1,'CLIENT',1,'tired',NULL,NULL,0.0000,'2026-02-13 01:33:32'),(2,1,'COUNSELOR',1,'tell me more',NULL,NULL,0.0000,'2026-02-13 01:33:32'),(3,1,'CLIENT',1,'상담 너무 힘들어요 그만하고 싶어요',NULL,NULL,0.0000,'2026-02-13 01:39:24'),(4,1,'CLIENT',1,'상담 너무 힘들어요 그만하고 싶어요',NULL,NULL,0.0000,'2026-02-13 01:48:37'),(7,1,'CLIENT',1,'상담 그만하고 싶어 힘들어',NULL,NULL,0.0000,'2026-02-13 02:04:07'),(8,1,'CLIENT',1,'안녕하세요',NULL,NULL,0.0000,'2026-02-13 04:41:51'),(9,1,'CLIENT',1,'너무 우울해요',NULL,NULL,0.0000,'2026-02-13 04:42:05'),(10,1,'CLIENT',1,'오늟  화가 난다',NULL,NULL,0.0000,'2026-02-13 04:42:20');
/*!40000 ALTER TABLE `msg` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `quality`
--

DROP TABLE IF EXISTS `quality`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `quality` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `sess_id` bigint NOT NULL,
  `flow` decimal(4,1) NOT NULL,
  `score` decimal(4,1) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_quality_sess` (`sess_id`),
  CONSTRAINT `fk_quality_sess` FOREIGN KEY (`sess_id`) REFERENCES `sess` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='quality';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `quality`
--

LOCK TABLES `quality` WRITE;
/*!40000 ALTER TABLE `quality` DISABLE KEYS */;
INSERT INTO `quality` VALUES (1,1,2.0,3.5,'2026-02-13 01:33:32');
/*!40000 ALTER TABLE `quality` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sess`
--

DROP TABLE IF EXISTS `sess`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sess` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `uuid` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `counselor_id` bigint NOT NULL,
  `client_id` bigint NOT NULL,
  `appt_id` bigint DEFAULT NULL,
  `channel` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'CHAT',
  `progress` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `start_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `end_at` timestamp NULL DEFAULT NULL,
  `end_reason` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `sat` tinyint(1) DEFAULT NULL,
  `sat_note` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ok_text` tinyint(1) NOT NULL DEFAULT '1',
  `ok_voice` tinyint(1) NOT NULL DEFAULT '0',
  `ok_face` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sess_uuid` (`uuid`),
  KEY `ix_sess_counselor_start` (`counselor_id`,`start_at`),
  KEY `ix_sess_client_start` (`client_id`,`start_at`),
  KEY `ix_sess_channel_progress` (`channel`,`progress`),
  KEY `fk_sess_appt` (`appt_id`),
  CONSTRAINT `fk_sess_appt` FOREIGN KEY (`appt_id`) REFERENCES `appt` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_sess_client` FOREIGN KEY (`client_id`) REFERENCES `client` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_sess_counselor` FOREIGN KEY (`counselor_id`) REFERENCES `counselor` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_sess_channel` CHECK ((`channel` in (_utf8mb4'CHAT',_utf8mb4'VOICE'))),
  CONSTRAINT `ck_sess_end_reason` CHECK (((`end_reason` is null) or (`end_reason` in (_utf8mb4'NORMAL',_utf8mb4'DROPOUT',_utf8mb4'TECH',_utf8mb4'UNKNOWN'))))
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='sess';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sess`
--

LOCK TABLES `sess` WRITE;
/*!40000 ALTER TABLE `sess` DISABLE KEYS */;
INSERT INTO `sess` VALUES (1,'S-UUID-0001',1,1,1,'CHAT','IN_PROGRESS','2026-02-13 01:33:32',NULL,NULL,NULL,NULL,1,0,0,'2026-02-13 01:33:32');
/*!40000 ALTER TABLE `sess` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `sess_analysis`
--

DROP TABLE IF EXISTS `sess_analysis`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sess_analysis` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `sess_id` bigint NOT NULL,
  `topic_id` bigint NOT NULL,
  `summary` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `note` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sess_topic` (`sess_id`,`topic_id`),
  KEY `ix_sess_analysis_time` (`sess_id`,`created_at`),
  KEY `fk_sess_analysis_topic` (`topic_id`),
  CONSTRAINT `fk_sess_analysis_sess` FOREIGN KEY (`sess_id`) REFERENCES `sess` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_sess_analysis_topic` FOREIGN KEY (`topic_id`) REFERENCES `topic` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='sess_analysis';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `sess_analysis`
--

LOCK TABLES `sess_analysis` WRITE;
/*!40000 ALTER TABLE `sess_analysis` DISABLE KEYS */;
/*!40000 ALTER TABLE `sess_analysis` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `stt`
--

DROP TABLE IF EXISTS `stt`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `stt` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `sess_id` bigint NOT NULL,
  `speaker` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `s_ms` int unsigned NOT NULL,
  `e_ms` int unsigned NOT NULL,
  `text` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `conf` decimal(5,4) NOT NULL DEFAULT '0.0000',
  `meta` json NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_stt_sess_time` (`sess_id`,`s_ms`,`e_ms`),
  KEY `ix_stt_speaker` (`speaker`),
  CONSTRAINT `fk_stt_sess` FOREIGN KEY (`sess_id`) REFERENCES `sess` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `ck_stt_speaker` CHECK ((`speaker` in (_utf8mb4'COUNSELOR',_utf8mb4'CLIENT')))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='stt';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `stt`
--

LOCK TABLES `stt` WRITE;
/*!40000 ALTER TABLE `stt` DISABLE KEYS */;
/*!40000 ALTER TABLE `stt` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `text_emotion`
--

DROP TABLE IF EXISTS `text_emotion`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `text_emotion` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `msg_id` bigint NOT NULL,
  `label` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `score` decimal(5,4) NOT NULL DEFAULT '0.0000',
  `meta` json NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_text_emotion_msg_time` (`msg_id`,`created_at`),
  KEY `ix_text_emotion_label` (`label`),
  CONSTRAINT `fk_text_emotion_msg` FOREIGN KEY (`msg_id`) REFERENCES `msg` (`id`) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='text_emotion';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `text_emotion`
--

LOCK TABLES `text_emotion` WRITE;
/*!40000 ALTER TABLE `text_emotion` DISABLE KEYS */;
/*!40000 ALTER TABLE `text_emotion` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `topic`
--

DROP TABLE IF EXISTS `topic`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `topic` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `code` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `descr` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_topic_code` (`code`),
  KEY `ix_topic_name` (`name`),
  KEY `ix_topic_type` (`type`),
  CONSTRAINT `ck_topic_type` CHECK ((`type` in (_utf8mb4'REGISTER',_utf8mb4'AI')))
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='topic';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `topic`
--

LOCK TABLES `topic` WRITE;
/*!40000 ALTER TABLE `topic` DISABLE KEYS */;
INSERT INTO `topic` VALUES (1,'T1','career','REGISTER','reg topic','2026-02-13 01:33:32'),(2,'T2','anxiety','AI','ai topic','2026-02-13 01:33:32');
/*!40000 ALTER TABLE `topic` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-02-14 15:27:38
