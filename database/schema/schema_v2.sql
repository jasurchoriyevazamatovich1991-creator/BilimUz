-- =====================================================================
-- BilimUz Database Schema v2.0
-- Chief Database Architect revision — enterprise audit trail + naming
-- =====================================================================
-- Every table: id (UUID), created_at, updated_at, deleted_at, status.
-- created_by / updated_by are added at the END of this script via a
-- PL/pgSQL loop (see "AUDIT FOREIGN KEYS" section) to avoid a circular
-- dependency: `roles` needs users.id for created_by, but `users` needs
-- roles.id for role_id. Creating all tables first, then wiring the
-- created_by/updated_by FKs in bulk, solves this cleanly and means a
-- newly added table needs zero manual FK wiring — the loop finds it
-- automatically by column name.
--
-- Naming convention:
--   tables       snake_case, plural            (test_attempts)
--   columns      snake_case                    (subject_id)
--   indexes      idx_<table>_<column>          (idx_tests_subject_id)
--   foreign keys fk_<table>_<column>           (fk_tests_subject_id)
--   unique       uq_<table>_<column>           (uq_users_email)
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =====================================================================
-- MODULE 2: USERS  (created before Roles/Authentication so later
-- modules can reference users.id; role_id FK is added after ROLES
-- exists, in the AUDIT FOREIGN KEYS-style bulk step below)
-- =====================================================================

CREATE TYPE user_gender AS ENUM ('male', 'female');
CREATE TYPE user_status AS ENUM ('active', 'inactive', 'banned', 'pending_verification');

CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_id       UUID NOT NULL,               -- FK to roles(id) added later (circular-dependency fix)
    first_name    VARCHAR(100) NOT NULL,
    last_name     VARCHAR(100) NOT NULL,
    phone         VARCHAR(20),
    email         VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,        -- bcrypt hash — never plaintext
    gender        user_gender,
    birth_date    DATE,
    image         TEXT,
    status        user_status NOT NULL DEFAULT 'pending_verification',
    created_by    UUID,
    updated_by    UUID,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at    TIMESTAMPTZ,
    CONSTRAINT uq_users_phone UNIQUE (phone),
    CONSTRAINT uq_users_email UNIQUE (email)
);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_phone ON users(phone);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_role_id ON users(role_id);
CREATE INDEX idx_users_created_at ON users(created_at);
CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE profiles (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL,
    bio                 TEXT,
    address             TEXT,
    telegram            VARCHAR(100),
    instagram           VARCHAR(100),
    website             VARCHAR(255),
    school_id           UUID,                 -- FK added after `schools` exists
    learning_center_id  UUID,                 -- FK added after `learning_centers` exists
    status              VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by          UUID,
    updated_by          UUID,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ,
    CONSTRAINT uq_profiles_user_id UNIQUE (user_id),
    CONSTRAINT fk_profiles_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_profiles_user_id ON profiles(user_id);

-- =====================================================================
-- MODULE 3: ROLES
-- =====================================================================

CREATE TABLE roles (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(50) NOT NULL,
    description TEXT,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by  UUID,
    updated_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_roles_name UNIQUE (name)
);
CREATE INDEX idx_roles_status ON roles(status);
CREATE TRIGGER trg_roles_updated_at BEFORE UPDATE ON roles
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Now that both tables exist, wire the circular FK:
ALTER TABLE users ADD CONSTRAINT fk_users_role_id FOREIGN KEY (role_id) REFERENCES roles(id);

-- =====================================================================
-- MODULE 4: PERMISSIONS
-- =====================================================================

CREATE TABLE permissions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(150) NOT NULL,
    code        VARCHAR(100) NOT NULL,          -- CREATE_TEST, DELETE_USER ...
    module      VARCHAR(50) NOT NULL,
    description TEXT,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by  UUID,
    updated_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_permissions_code UNIQUE (code)
);
CREATE INDEX idx_permissions_module ON permissions(module);

-- Association table promoted to a full entity (id + audit + status)
-- instead of a bare composite-PK junction — deliberate trade-off: it
-- costs one extra UUID + index per grant, but gives a complete audit
-- trail of *who granted which permission to which role and when*,
-- which enterprise/compliance review (banking-grade, per the brief)
-- expects. A pure junction table would not support this.
CREATE TABLE role_permissions (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role_id       UUID NOT NULL,
    permission_id UUID NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by    UUID,
    updated_by    UUID,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at    TIMESTAMPTZ,
    CONSTRAINT uq_role_permissions_role_permission UNIQUE (role_id, permission_id),
    CONSTRAINT fk_role_permissions_role_id FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    CONSTRAINT fk_role_permissions_permission_id FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
);
CREATE INDEX idx_role_permissions_role_id ON role_permissions(role_id);
CREATE INDEX idx_role_permissions_permission_id ON role_permissions(permission_id);

-- =====================================================================
-- MODULE 1: AUTHENTICATION — sessions, refresh_tokens, login_history,
-- verification_codes — event-log tables. Deliberately NOT given
-- created_by/updated_by beyond user_id itself: the "creator" of a
-- login-history row IS the user_id, duplicating it as created_by adds
-- no audit value. status is included per rule, expressing lifecycle
-- where one exists (token revoked, code used); log rows use 'logged'.
-- =====================================================================

CREATE TABLE sessions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL,
    token_hash  VARCHAR(255) NOT NULL,
    device      VARCHAR(150),
    browser     VARCHAR(150),
    ip_address  INET,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_sessions_token_hash UNIQUE (token_hash),
    CONSTRAINT fk_sessions_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_status ON sessions(status);

CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL,
    token_hash  VARCHAR(255) NOT NULL,
    jti         VARCHAR(64) NOT NULL,
    user_agent  VARCHAR(255),
    ip_address  INET,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',   -- active | revoked
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_refresh_tokens_token_hash UNIQUE (token_hash),
    CONSTRAINT uq_refresh_tokens_jti UNIQUE (jti),
    CONSTRAINT fk_refresh_tokens_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_status ON refresh_tokens(status);

CREATE TABLE login_history (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL,
    ip_address  INET,
    device      VARCHAR(150),
    browser     VARCHAR(150),
    country     VARCHAR(100),
    city        VARCHAR(100),
    status      VARCHAR(20) NOT NULL DEFAULT 'logged',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT fk_login_history_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_login_history_user_id ON login_history(user_id);
CREATE INDEX idx_login_history_created_at ON login_history(created_at);

CREATE TABLE verification_codes (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL,
    destination VARCHAR(255) NOT NULL,
    code_hash   VARCHAR(255) NOT NULL,
    purpose     VARCHAR(30) NOT NULL,
    attempts    SMALLINT NOT NULL DEFAULT 0,
    status      VARCHAR(20) NOT NULL DEFAULT 'pending',   -- pending | used | expired
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT fk_verification_codes_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_verification_codes_user_id ON verification_codes(user_id);
CREATE INDEX idx_verification_codes_status ON verification_codes(status);

CREATE TABLE password_history (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id        UUID NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,
    status         VARCHAR(20) NOT NULL DEFAULT 'logged',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at     TIMESTAMPTZ,
    CONSTRAINT fk_password_history_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_password_history_user_id ON password_history(user_id, created_at);

-- =====================================================================
-- MODULE 5: SCHOOLS
-- =====================================================================

CREATE TABLE schools (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(255) NOT NULL,
    region      VARCHAR(100),
    district    VARCHAR(100),
    address     TEXT,
    phone       VARCHAR(20),
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by  UUID,
    updated_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ
);
CREATE INDEX idx_schools_region ON schools(region);
CREATE INDEX idx_schools_status ON schools(status);

ALTER TABLE profiles ADD CONSTRAINT fk_profiles_school_id FOREIGN KEY (school_id) REFERENCES schools(id);

-- =====================================================================
-- MODULE 6: LEARNING CENTERS
-- =====================================================================

CREATE TABLE learning_centers (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(255) NOT NULL,
    owner_name  VARCHAR(255),
    phone       VARCHAR(20),
    region      VARCHAR(100),
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by  UUID,
    updated_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ
);
CREATE INDEX idx_learning_centers_region ON learning_centers(region);
CREATE INDEX idx_learning_centers_status ON learning_centers(status);

ALTER TABLE profiles ADD CONSTRAINT fk_profiles_learning_center_id FOREIGN KEY (learning_center_id) REFERENCES learning_centers(id);

-- =====================================================================
-- MODULE 7: SUBJECTS
-- =====================================================================

CREATE TABLE subjects (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(150) NOT NULL,
    icon        TEXT,
    color       VARCHAR(20),
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by  UUID,
    updated_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_subjects_name UNIQUE (name)
);
CREATE INDEX idx_subjects_status ON subjects(status);

-- =====================================================================
-- MODULE 8: GRADES
-- =====================================================================

CREATE TABLE grades (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(100) NOT NULL,   -- 5-sinf ... Attestatsiya, Abituriyent
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by  UUID,
    updated_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_grades_name UNIQUE (name)
);

-- =====================================================================
-- MODULE 9: TOPICS
-- =====================================================================

CREATE TABLE topics (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_id   UUID NOT NULL,
    grade_id     UUID,
    title        VARCHAR(255) NOT NULL,
    description  TEXT,
    order_number INT NOT NULL DEFAULT 0,
    status       VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by   UUID,
    updated_by   UUID,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at   TIMESTAMPTZ,
    CONSTRAINT fk_topics_subject_id FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    CONSTRAINT fk_topics_grade_id FOREIGN KEY (grade_id) REFERENCES grades(id)
);
CREATE INDEX idx_topics_subject_id ON topics(subject_id);
CREATE INDEX idx_topics_grade_id ON topics(grade_id);

-- =====================================================================
-- MODULE 10: LESSONS
-- =====================================================================

CREATE TABLE lessons (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic_id    UUID NOT NULL,
    title       VARCHAR(255) NOT NULL,
    video       TEXT,
    pdf         TEXT,
    content     TEXT,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by  UUID,
    updated_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT fk_lessons_topic_id FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
);
CREATE INDEX idx_lessons_topic_id ON lessons(topic_id);

-- =====================================================================
-- MODULE 11: TESTS
-- =====================================================================

CREATE TYPE difficulty_level AS ENUM ('easy', 'medium', 'hard');
CREATE TYPE test_status AS ENUM ('draft', 'published', 'archived');

CREATE TABLE tests (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subject_id        UUID,
    grade_id          UUID,
    topic_id          UUID,
    title             VARCHAR(255) NOT NULL,
    description       TEXT,
    difficulty        difficulty_level NOT NULL DEFAULT 'medium',
    duration          INT NOT NULL DEFAULT 60,
    question_count    INT NOT NULL DEFAULT 0,
    passing_score     NUMERIC(6,2),
    shuffle_questions BOOLEAN NOT NULL DEFAULT TRUE,
    shuffle_answers   BOOLEAN NOT NULL DEFAULT TRUE,
    status            test_status NOT NULL DEFAULT 'draft',
    created_by        UUID,
    updated_by        UUID,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at        TIMESTAMPTZ,
    CONSTRAINT fk_tests_subject_id FOREIGN KEY (subject_id) REFERENCES subjects(id),
    CONSTRAINT fk_tests_grade_id FOREIGN KEY (grade_id) REFERENCES grades(id),
    CONSTRAINT fk_tests_topic_id FOREIGN KEY (topic_id) REFERENCES topics(id)
);
CREATE INDEX idx_tests_subject_id ON tests(subject_id);
CREATE INDEX idx_tests_status ON tests(status);
CREATE INDEX idx_tests_created_at ON tests(created_at);
CREATE TRIGGER trg_tests_updated_at BEFORE UPDATE ON tests
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =====================================================================
-- MODULE 12: QUESTIONS
-- =====================================================================

CREATE TYPE question_type AS ENUM ('single_choice', 'multiple_choice', 'true_false', 'short_answer', 'essay');

CREATE TABLE questions (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    test_id       UUID NOT NULL,
    question_text TEXT NOT NULL,
    question_type question_type NOT NULL DEFAULT 'single_choice',
    difficulty    difficulty_level NOT NULL DEFAULT 'medium',
    score         NUMERIC(6,2) NOT NULL DEFAULT 1,
    explanation   TEXT,
    status        VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by    UUID,
    updated_by    UUID,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at    TIMESTAMPTZ,
    CONSTRAINT fk_questions_test_id FOREIGN KEY (test_id) REFERENCES tests(id) ON DELETE CASCADE
);
CREATE INDEX idx_questions_test_id ON questions(test_id);

-- =====================================================================
-- MODULE 13: QUESTION OPTIONS
-- =====================================================================

CREATE TABLE question_options (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    question_id UUID NOT NULL,
    option_text TEXT NOT NULL,
    is_correct  BOOLEAN NOT NULL DEFAULT FALSE,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by  UUID,
    updated_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT fk_question_options_question_id FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);
CREATE INDEX idx_question_options_question_id ON question_options(question_id);

-- =====================================================================
-- MODULE 14: QUESTION MEDIA
-- =====================================================================

CREATE TABLE question_media (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    question_id UUID NOT NULL,
    media_type  VARCHAR(20) NOT NULL,   -- image | audio | video | formula
    file_url    TEXT NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by  UUID,
    updated_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT fk_question_media_question_id FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);
CREATE INDEX idx_question_media_question_id ON question_media(question_id);

-- =====================================================================
-- MODULE 15: TEST ATTEMPTS
-- =====================================================================

CREATE TYPE attempt_status AS ENUM ('in_progress', 'paused', 'submitted', 'auto_finished', 'cancelled');

CREATE TABLE test_attempts (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL,
    test_id      UUID NOT NULL,
    start_time   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finish_time  TIMESTAMPTZ,
    score        NUMERIC(8,2),
    percentage   NUMERIC(5,2),
    status       attempt_status NOT NULL DEFAULT 'in_progress',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at   TIMESTAMPTZ,
    CONSTRAINT fk_test_attempts_user_id FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_test_attempts_test_id FOREIGN KEY (test_id) REFERENCES tests(id)
);
CREATE INDEX idx_test_attempts_user_id ON test_attempts(user_id);
CREATE INDEX idx_test_attempts_test_id ON test_attempts(test_id);
CREATE INDEX idx_test_attempts_status ON test_attempts(status);

CREATE TABLE answers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    attempt_id      UUID NOT NULL,
    question_id     UUID NOT NULL,
    selected_option UUID,
    is_correct      BOOLEAN,
    status          VARCHAR(20) NOT NULL DEFAULT 'answered',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    CONSTRAINT uq_answers_attempt_question UNIQUE (attempt_id, question_id),
    CONSTRAINT fk_answers_attempt_id FOREIGN KEY (attempt_id) REFERENCES test_attempts(id) ON DELETE CASCADE,
    CONSTRAINT fk_answers_question_id FOREIGN KEY (question_id) REFERENCES questions(id),
    CONSTRAINT fk_answers_selected_option FOREIGN KEY (selected_option) REFERENCES question_options(id)
);
CREATE INDEX idx_answers_attempt_id ON answers(attempt_id);

-- =====================================================================
-- MODULE 16: RESULTS
-- =====================================================================

CREATE TABLE results (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    attempt_id  UUID NOT NULL,
    user_id     UUID NOT NULL,
    test_id     UUID NOT NULL,
    score       NUMERIC(8,2) NOT NULL,
    percentage  NUMERIC(5,2) NOT NULL,
    is_passed   BOOLEAN,
    status      VARCHAR(20) NOT NULL DEFAULT 'final',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_results_attempt_id UNIQUE (attempt_id),
    CONSTRAINT fk_results_attempt_id FOREIGN KEY (attempt_id) REFERENCES test_attempts(id) ON DELETE CASCADE,
    CONSTRAINT fk_results_user_id FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_results_test_id FOREIGN KEY (test_id) REFERENCES tests(id)
);
CREATE INDEX idx_results_user_id ON results(user_id);
CREATE INDEX idx_results_test_id ON results(test_id);

CREATE TABLE statistics (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL,
    subject_id      UUID,
    tests_taken     INT NOT NULL DEFAULT 0,
    correct_answers INT NOT NULL DEFAULT 0,
    wrong_answers   INT NOT NULL DEFAULT 0,
    avg_score       NUMERIC(6,2),
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    CONSTRAINT fk_statistics_user_id FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_statistics_subject_id FOREIGN KEY (subject_id) REFERENCES subjects(id)
);
CREATE INDEX idx_statistics_user_id ON statistics(user_id);

CREATE TABLE ranking (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL,
    subject_id  UUID,
    period      VARCHAR(20) NOT NULL DEFAULT 'all_time',
    score       NUMERIC(10,2) NOT NULL DEFAULT 0,
    rank        INT,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT fk_ranking_user_id FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_ranking_subject_id FOREIGN KEY (subject_id) REFERENCES subjects(id)
);
CREATE INDEX idx_ranking_subject_id ON ranking(subject_id, period);
CREATE INDEX idx_ranking_user_id ON ranking(user_id);

CREATE TABLE badges (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(150) NOT NULL,
    icon        TEXT,
    description TEXT,
    criteria    JSONB,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by  UUID,
    updated_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ
);

CREATE TABLE achievements (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL,
    badge_id    UUID NOT NULL,
    earned_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_achievements_user_badge UNIQUE (user_id, badge_id),
    CONSTRAINT fk_achievements_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_achievements_badge_id FOREIGN KEY (badge_id) REFERENCES badges(id)
);
CREATE INDEX idx_achievements_user_id ON achievements(user_id);

-- =====================================================================
-- MODULE 17: CERTIFICATES
-- =====================================================================

CREATE TABLE certificate_templates (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(150) NOT NULL,
    design      JSONB,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by  UUID,
    updated_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ
);

CREATE TABLE certificates (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id            UUID NOT NULL,
    result_id          UUID NOT NULL,
    template_id        UUID,
    certificate_number VARCHAR(50) NOT NULL,
    pdf_url            TEXT,
    status              VARCHAR(20) NOT NULL DEFAULT 'issued',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at         TIMESTAMPTZ,
    CONSTRAINT uq_certificates_certificate_number UNIQUE (certificate_number),
    CONSTRAINT fk_certificates_user_id FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_certificates_result_id FOREIGN KEY (result_id) REFERENCES results(id),
    CONSTRAINT fk_certificates_template_id FOREIGN KEY (template_id) REFERENCES certificate_templates(id)
);
CREATE INDEX idx_certificates_user_id ON certificates(user_id);

CREATE TABLE certificate_verification (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    certificate_id    UUID NOT NULL,
    verification_code VARCHAR(50) NOT NULL,
    verified_count    INT NOT NULL DEFAULT 0,
    last_verified_at  TIMESTAMPTZ,
    last_verified_ip  INET,
    status            VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at        TIMESTAMPTZ,
    CONSTRAINT uq_certificate_verification_code UNIQUE (verification_code),
    CONSTRAINT fk_certificate_verification_certificate_id FOREIGN KEY (certificate_id) REFERENCES certificates(id) ON DELETE CASCADE
);

-- =====================================================================
-- MODULE 18: PAYMENTS
-- =====================================================================

CREATE TABLE plans (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name          VARCHAR(100) NOT NULL,
    price         NUMERIC(12,2) NOT NULL,
    duration_days INT NOT NULL,
    features      JSONB,
    status        VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by    UUID,
    updated_by    UUID,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at    TIMESTAMPTZ
);

CREATE TYPE subscription_status AS ENUM ('active', 'expired', 'cancelled');

CREATE TABLE subscriptions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL,
    plan_id     UUID NOT NULL,
    start_date  TIMESTAMPTZ NOT NULL DEFAULT now(),
    end_date    TIMESTAMPTZ NOT NULL,
    status      subscription_status NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT fk_subscriptions_user_id FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_subscriptions_plan_id FOREIGN KEY (plan_id) REFERENCES plans(id)
);
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);

CREATE TYPE payment_provider AS ENUM ('click', 'payme', 'uzum_bank', 'humo', 'uzcard', 'stripe');
CREATE TYPE payment_status AS ENUM ('pending', 'success', 'failed', 'refunded', 'cancelled');

CREATE TABLE payments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL,
    subscription_id UUID,
    provider        payment_provider NOT NULL,
    amount          NUMERIC(12,2) NOT NULL,
    currency        VARCHAR(10) NOT NULL DEFAULT 'UZS',
    status          payment_status NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    CONSTRAINT fk_payments_user_id FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_payments_subscription_id FOREIGN KEY (subscription_id) REFERENCES subscriptions(id)
);
CREATE INDEX idx_payments_user_id ON payments(user_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_created_at ON payments(created_at);
CREATE TRIGGER trg_payments_updated_at BEFORE UPDATE ON payments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE transactions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_id      UUID NOT NULL,
    provider_txn_id VARCHAR(255),
    raw_response    JSONB,
    status          VARCHAR(20) NOT NULL DEFAULT 'recorded',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    CONSTRAINT fk_transactions_payment_id FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE CASCADE
);
CREATE INDEX idx_transactions_payment_id ON transactions(payment_id);

-- =====================================================================
-- MODULE 19: NOTIFICATIONS
-- =====================================================================

CREATE TABLE notification_templates (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code        VARCHAR(100) NOT NULL,
    channel     VARCHAR(20) NOT NULL,
    subject     VARCHAR(255),
    body        TEXT NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by  UUID,
    updated_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_notification_templates_code UNIQUE (code)
);

CREATE TABLE notifications (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL,
    title       VARCHAR(255) NOT NULL,
    message     TEXT NOT NULL,
    channel     VARCHAR(20) NOT NULL DEFAULT 'in_app',
    is_read     BOOLEAN NOT NULL DEFAULT FALSE,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT fk_notifications_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_notifications_user_id ON notifications(user_id, is_read);

CREATE TYPE queue_status AS ENUM ('pending', 'sent', 'failed');

CREATE TABLE email_queue (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    to_email    VARCHAR(255) NOT NULL,
    subject     VARCHAR(255) NOT NULL,
    body        TEXT NOT NULL,
    attempts    SMALLINT NOT NULL DEFAULT 0,
    sent_at     TIMESTAMPTZ,
    status      queue_status NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ
);
CREATE INDEX idx_email_queue_status ON email_queue(status);

CREATE TABLE sms_queue (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    to_phone    VARCHAR(20) NOT NULL,
    message     VARCHAR(500) NOT NULL,
    attempts    SMALLINT NOT NULL DEFAULT 0,
    sent_at     TIMESTAMPTZ,
    status      queue_status NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ
);
CREATE INDEX idx_sms_queue_status ON sms_queue(status);

-- =====================================================================
-- MODULE 20: ANALYTICS
-- =====================================================================

CREATE TABLE daily_statistics (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL,
    subject_id      UUID,
    stat_date       DATE NOT NULL,
    tests_taken     INT NOT NULL DEFAULT 0,
    correct_answers INT NOT NULL DEFAULT 0,
    wrong_answers   INT NOT NULL DEFAULT 0,
    status          VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    CONSTRAINT uq_daily_statistics_user_subject_date UNIQUE (user_id, subject_id, stat_date),
    CONSTRAINT fk_daily_statistics_user_id FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_daily_statistics_subject_id FOREIGN KEY (subject_id) REFERENCES subjects(id)
);
CREATE INDEX idx_daily_statistics_user_id ON daily_statistics(user_id, stat_date);

CREATE TABLE monthly_statistics (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL,
    subject_id  UUID,
    month       SMALLINT NOT NULL,
    year        SMALLINT NOT NULL,
    tests_taken INT NOT NULL DEFAULT 0,
    avg_score   NUMERIC(6,2),
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_monthly_statistics_user_subject_month_year UNIQUE (user_id, subject_id, month, year),
    CONSTRAINT fk_monthly_statistics_user_id FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX idx_monthly_statistics_user_id ON monthly_statistics(user_id, year, month);

-- =====================================================================
-- MODULE 21: AI
-- =====================================================================

CREATE TABLE ai_chats (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL,
    title       VARCHAR(255),
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT fk_ai_chats_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_ai_chats_user_id ON ai_chats(user_id);

CREATE TABLE ai_history (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_id     UUID NOT NULL,
    role        VARCHAR(20) NOT NULL,
    message     TEXT NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT fk_ai_history_chat_id FOREIGN KEY (chat_id) REFERENCES ai_chats(id) ON DELETE CASCADE
);
CREATE INDEX idx_ai_history_chat_id ON ai_history(chat_id);

CREATE TABLE ai_recommendations (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL,
    subject_id  UUID,
    text        TEXT NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT fk_ai_recommendations_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_ai_recommendations_user_id ON ai_recommendations(user_id);

CREATE TABLE study_plans (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL,
    subject_id  UUID,
    plan        JSONB NOT NULL,
    start_date  DATE NOT NULL,
    end_date    DATE NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT fk_study_plans_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_study_plans_user_id ON study_plans(user_id);

-- =====================================================================
-- MODULE 22: SETTINGS
-- =====================================================================

CREATE TABLE general_settings (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key         VARCHAR(150) NOT NULL,
    value       JSONB NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by  UUID,
    updated_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_general_settings_key UNIQUE (key)
);

CREATE TABLE smtp_settings (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    host        VARCHAR(255) NOT NULL,
    port        INT NOT NULL DEFAULT 587,
    username    VARCHAR(255),
    password    VARCHAR(255),               -- encrypted at rest by app layer
    from_email  VARCHAR(255),
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by  UUID,
    updated_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ
);

CREATE TABLE payment_settings (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider    payment_provider NOT NULL,
    merchant_id VARCHAR(255),
    secret_key  VARCHAR(255),               -- encrypted at rest by app layer
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by  UUID,
    updated_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT uq_payment_settings_provider UNIQUE (provider)
);

CREATE TABLE ai_settings (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider    VARCHAR(100) NOT NULL,
    api_key     VARCHAR(255),               -- encrypted at rest by app layer
    model       VARCHAR(100),
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_by  UUID,
    updated_by  UUID,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ
);

-- =====================================================================
-- MODULE 23: UPLOADS
-- =====================================================================

CREATE TABLE uploads (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID,
    file_name   VARCHAR(255) NOT NULL,
    file_url    TEXT NOT NULL,
    file_type   VARCHAR(30) NOT NULL,
    size_bytes  BIGINT,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT fk_uploads_user_id FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX idx_uploads_user_id ON uploads(user_id);

CREATE TABLE images (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    upload_id   UUID NOT NULL,
    width       INT,
    height      INT,
    alt_text    VARCHAR(255),
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT fk_images_upload_id FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE
);

CREATE TABLE videos (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    upload_id        UUID NOT NULL,
    duration_seconds INT,
    thumbnail_url    TEXT,
    status           VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at       TIMESTAMPTZ,
    CONSTRAINT fk_videos_upload_id FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE
);

CREATE TABLE documents (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    upload_id   UUID NOT NULL,
    page_count  INT,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT fk_documents_upload_id FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE
);

-- =====================================================================
-- MODULE 24: AUDIT LOGS
-- =====================================================================

CREATE TABLE audit_logs (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID,
    action      VARCHAR(100) NOT NULL,      -- test.create, user.ban ...
    entity_type VARCHAR(100),
    entity_id   UUID,
    ip_address  INET,
    metadata    JSONB,
    status      VARCHAR(20) NOT NULL DEFAULT 'logged',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    CONSTRAINT fk_audit_logs_user_id FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- =====================================================================
-- MODULE 25: SYSTEM LOGS
-- =====================================================================

CREATE TABLE system_logs (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    level       VARCHAR(20) NOT NULL,        -- info | warning | error | critical
    source      VARCHAR(100),
    message     TEXT NOT NULL,
    context     JSONB,
    status      VARCHAR(20) NOT NULL DEFAULT 'logged',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ
);
CREATE INDEX idx_system_logs_level ON system_logs(level, created_at);

-- =====================================================================
-- AUDIT FOREIGN KEYS — bulk-wire created_by / updated_by to users(id)
-- =====================================================================
-- Runs once, after every table exists. Any NEW table added later that
-- includes created_by/updated_by columns is picked up automatically the
-- next time this block (or its Alembic equivalent) runs — no manual
-- ALTER TABLE needed per module.

DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_name IN ('created_by', 'updated_by')
          AND table_name != 'users'   -- users.created_by/updated_by self-reference, handled separately
    LOOP
        EXECUTE format(
            'ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES users(id) ON DELETE SET NULL',
            r.table_name,
            'fk_' || r.table_name || '_' || r.column_name,
            r.column_name
        );
    END LOOP;
END $$;

-- users.created_by/updated_by are self-referencing — added separately
-- since the loop above deliberately skips the `users` table.
ALTER TABLE users ADD CONSTRAINT fk_users_created_by FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE users ADD CONSTRAINT fk_users_updated_by FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL;

-- =====================================================================
-- SEED
-- =====================================================================

INSERT INTO roles (name, description) VALUES
    ('Super Admin', 'Platforma egasi'),
    ('Admin', 'Platformani boshqaradi'),
    ('Moderator', 'Muayyan fanlarni boshqaradi'),
    ('Teacher', 'Testlar va natijalar bilan ishlaydi'),
    ('Applicant', 'Abituriyent'),
    ('Student', 'O''quvchi'),
    ('Parent', 'Ota-ona'),
    ('Guest', 'Ro''yxatdan o''tmagan foydalanuvchi');

INSERT INTO general_settings (key, value) VALUES
    ('platform_name', '"BilimUz"'),
    ('default_language', '"uz"'),
    ('maintenance_mode', 'false');
