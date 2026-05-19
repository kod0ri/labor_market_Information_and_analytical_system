CREATE TABLE analytics.daily_market_snapshots (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    category VARCHAR(100),
    total_vacancies INTEGER,
    total_resumes INTEGER,
    avg_vacancy_salary_usd NUMERIC, -- Змінено на USD
    avg_resume_salary_usd NUMERIC,  -- Змінено на USD
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(snapshot_date, category)
);