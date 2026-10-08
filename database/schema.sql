-- AI Voice Coach Database Schema
-- Run this file to create the required tables

CREATE DATABASE IF NOT EXISTS ai_voice_coach;
USE ai_voice_coach;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Interviews table
CREATE TABLE IF NOT EXISTS interviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    interview_type VARCHAR(50) NOT NULL DEFAULT 'practice',
    overall_score INT DEFAULT 0,
    questions_count INT DEFAULT 0,
    role VARCHAR(100) NULL,
    experience VARCHAR(50) NULL,
    difficulty VARCHAR(20) NULL,
    communication INT NULL,
    confidence INT NULL,
    clarity INT NULL,
    grammar INT NULL,
    structure INT NULL,
    relevance INT NULL,
    details JSON NULL,
    strengths JSON NULL,
    improvements JSON NULL,
    overall_feedback TEXT NULL,
    session_type VARCHAR(20) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
