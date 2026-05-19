-- =============================================================================
-- Міграція: відсутні constraints та індекси
-- Файл: init_db/07_constraints_and_indexes.sql
-- =============================================================================

-- -----------------------------------------------------------------------
-- 1. UNIQUE на staging_id у core таблицях.
--    Гарантує 1:1 відношення staging → core.
--    Без цього один staging-запис міг дати N core-записів при повторних запусках.
-- -----------------------------------------------------------------------
ALTER TABLE core.vacancies
    ADD CONSTRAINT uq_vacancies_staging_id UNIQUE (staging_id);

ALTER TABLE core.resumes
    ADD CONSTRAINT uq_resumes_staging_id UNIQUE (staging_id);

-- -----------------------------------------------------------------------
-- 2. Partial index для currency_converter — лише записи, що потребують конвертації.
--    Без нього currency_converter робить full scan core.vacancies/resumes на кожному запуску.
-- -----------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_vacancies_pending_conversion
    ON core.vacancies (id)
    WHERE currency IS NOT NULL
      AND (min_salary IS NOT NULL OR max_salary IS NOT NULL)
      AND min_salary_usd_eq IS NULL
      AND max_salary_usd_eq IS NULL;

CREATE INDEX IF NOT EXISTS idx_resumes_pending_conversion
    ON core.resumes (id)
    WHERE currency IS NOT NULL
      AND (min_salary IS NOT NULL OR max_salary IS NOT NULL)
      AND min_salary_usd_eq IS NULL
      AND max_salary_usd_eq IS NULL;

-- -----------------------------------------------------------------------
-- 3. Індекс на snapshot_date для діапазонних запитів з React API.
--    UNIQUE constraint (snapshot_date, category) вже є, але він не покриває
--    запити типу WHERE snapshot_date BETWEEN $1 AND $2 без category.
-- -----------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_snapshots_date
    ON analytics.daily_market_snapshots (snapshot_date DESC);
