-- =============================================================================
-- Міграція: схема auth + таблиця користувачів системи
-- Файл: init_db/08_auth_users.sql
-- =============================================================================
--
-- До цієї міграції автентифікація працювала на одному захардкодженому
-- акаунті з env (ADMIN_USERNAME / ADMIN_PASSWORD), пароль звірявся у відкритому
-- вигляді. Тепер користувачі зберігаються в БД, пароль — лише як хеш
-- (pbkdf2_sha256, див. src/auth/security.py).
--
-- ВАЖЛИВО: init_db/*.sql виконуються лише при першій ініціалізації БД
-- (порожній том postgres_data). Для вже наповненої бази ця ж схема
-- створюється ідемпотентно на старті застосунку — src/auth/bootstrap.py.
-- -----------------------------------------------------------------------------

-- Усі акаунти системи — адміністратори з повним доступом до панелі,
-- статистики й метрик. Ролей немає; звичайних користувачів не передбачено.

CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS auth.users (
    id            INTEGER     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username      VARCHAR(64) NOT NULL,
    password_hash TEXT        NOT NULL,
    is_active     BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at  TIMESTAMPTZ
);

-- Унікальність логіна без урахування регістру: 'Admin' == 'admin'
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_lower
    ON auth.users (lower(username));

-- Швидкий підрахунок «онлайн» користувачів (last_seen_at за останні N хвилин)
CREATE INDEX IF NOT EXISTS idx_users_last_seen
    ON auth.users (last_seen_at DESC);
