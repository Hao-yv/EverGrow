-- EverGrow 数据库初始化脚本
-- MySQL 8.0+ / MariaDB 10.3+
-- 使用前请先创建数据库: CREATE DATABASE evergrow_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- 推荐使用: python scripts/init_db.py（含初始 admin 用户）

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS `knowledge_articles` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `chroma_doc_id` VARCHAR(64) NOT NULL COMMENT 'Chroma 文档 ID',
  `title` VARCHAR(200) NOT NULL COMMENT '问题/标题',
  `stage` VARCHAR(30) NULL COMMENT '年龄段',
  `category` VARCHAR(30) NULL COMMENT '矛盾类型',
  `source_file` VARCHAR(255) NULL COMMENT '原始文件名',
  `source_author` VARCHAR(100) NULL COMMENT '作者/机构',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_chroma_doc_id` (`chroma_doc_id`),
  KEY `idx_stage_category` (`stage`, `category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识条目元数据';

CREATE TABLE IF NOT EXISTS `users` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(50) NOT NULL COMMENT '用户名',
  `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希',
  `nickname` VARCHAR(50) NULL COMMENT '昵称',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户';

CREATE TABLE IF NOT EXISTS `conversations` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NULL COMMENT '用户，匿名为空',
  `session_id` VARCHAR(64) NULL COMMENT '匿名会话标识',
  `title` VARCHAR(100) NULL COMMENT '会话摘要',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_session_id` (`session_id`),
  CONSTRAINT `fk_conv_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='问答会话';

CREATE TABLE IF NOT EXISTS `conversation_messages` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `conversation_id` BIGINT NOT NULL COMMENT '所属会话',
  `role` ENUM('user','assistant') NOT NULL COMMENT '角色',
  `content` TEXT NOT NULL COMMENT '消息内容',
  `retrieved_doc_ids` JSON NULL COMMENT '引用的 chroma_doc_id 列表',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_conversation_id` (`conversation_id`),
  CONSTRAINT `fk_cm_conversation` FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会话消息';

SET FOREIGN_KEY_CHECKS = 1;
