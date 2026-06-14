-- =============================================================================
-- Міграція: анонімний трекінг відвідувачів сайту
-- Файл: init_db/09_visits.sql
-- =============================================================================
--
-- Рахуємо ВСІХ відвідувачів (включно з незареєстрованими) для метрик адмінпанелі:
-- скільки людей на сайті зараз, за 24 год, за тиждень, середній онлайн.
--
-- visitor_id — випадковий ідентифікатор браузера з localStorage (НЕ персональні
-- дані). IP та query-рядки не зберігаються. Схема analytics створена у 00_schemas.sql.
-- Для вже наповнених баз таблиця створюється на старті — src/tracking/bootstrap.py.
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS analytics.visits (
    id         BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    visitor_id UUID        NOT NULL,
    path       VARCHAR(200),
    seen_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_visits_seen_at
    ON analytics.visits (seen_at DESC);

CREATE INDEX IF NOT EXISTS idx_visits_visitor_seen
    ON analytics.visits (visitor_id, seen_at DESC);
