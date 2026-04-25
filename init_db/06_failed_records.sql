-- =============================================================================
-- Міграція: таблиця failed_records + очищення raw_html після обробки
-- Файл: init_db/06_failed_records.sql
-- =============================================================================

-- -----------------------------------------------------------------------
-- Таблиця для запису невдалих спроб обробки.
-- Замість "🔴 помилка в консоль і забули" — зберігаємо в БД для retry/аудиту.
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS staging.failed_records (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    record_type     VARCHAR(20)  NOT NULL CHECK (record_type IN ('vacancy', 'resume')),
    staging_id      INTEGER      NOT NULL,   -- посилання на raw_vacancies або raw_resumes
    failed_at       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    attempt_count   SMALLINT     DEFAULT 1,
    error_type      VARCHAR(50),             -- 'validation', 'rate_limit', 'unknown'
    error_detail    TEXT,                    -- повне повідомлення помилки
    is_resolved     BOOLEAN      DEFAULT FALSE,
    resolved_at     TIMESTAMP
);

-- Індекс для швидкого пошуку невирішених помилок по типу
CREATE INDEX IF NOT EXISTS idx_failed_records_unresolved
    ON staging.failed_records (record_type, is_resolved)
    WHERE is_resolved = FALSE;

-- Унікальність: один активний запис на staging_id + тип
-- При повторній помилці — оновлюємо існуючий (upsert по цьому constraint)
CREATE UNIQUE INDEX IF NOT EXISTS idx_failed_records_active
    ON staging.failed_records (record_type, staging_id)
    WHERE is_resolved = FALSE;