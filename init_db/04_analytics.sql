-- Щоденний зріз ринку (для побудови графіків)
CREATE TABLE analytics.daily_market_snapshots (
    snapshot_date DATE NOT NULL,
    location_id INTEGER REFERENCES dictionaries.locations(id),
    skill_id INTEGER REFERENCES dictionaries.skills(id),
    active_vacancies_count INTEGER DEFAULT 0,
    active_resumes_count INTEGER DEFAULT 0,
    avg_offered_salary NUMERIC(10, 2),
    PRIMARY KEY (snapshot_date, location_id, skill_id)
);