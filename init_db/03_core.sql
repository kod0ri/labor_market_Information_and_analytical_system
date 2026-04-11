-- Очищені вакансії
CREATE TABLE core.vacancies (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id INTEGER REFERENCES dictionaries.sources(id),
    external_id VARCHAR(100) NOT NULL,
    company_id INTEGER REFERENCES dictionaries.companies(id),
    location_id INTEGER REFERENCES dictionaries.locations(id),
    title VARCHAR(255) NOT NULL,
    experience_level VARCHAR(50),   -- Junior, Middle, Senior
    employment_type VARCHAR(50),    -- Remote, Office, Part-time
    min_salary NUMERIC(10, 2),
    max_salary NUMERIC(10, 2),
    currency VARCHAR(10),
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Забороняємо дублікати тієї самої вакансії з того самого джерела
    CONSTRAINT uq_vacancy_source UNIQUE (source_id, external_id)
);

-- Зв'язок: Які навички вимагаються у вакансії (Багато-до-Багатьох)
CREATE TABLE core.vacancy_skills (
    vacancy_id INTEGER REFERENCES core.vacancies(id) ON DELETE CASCADE,
    skill_id INTEGER REFERENCES dictionaries.skills(id) ON DELETE CASCADE,
    PRIMARY KEY (vacancy_id, skill_id)
);

-- Очищені резюме
CREATE TABLE core.resumes (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id INTEGER REFERENCES dictionaries.sources(id),
    external_id VARCHAR(100) NOT NULL,
    location_id INTEGER REFERENCES dictionaries.locations(id),
    desired_position VARCHAR(255) NOT NULL,
    expected_salary NUMERIC(10, 2),
    currency VARCHAR(10),
    total_experience_months INTEGER,
    updated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_resume_source UNIQUE (source_id, external_id)
);

-- Зв'язок: Які навички має кандидат (Багато-до-Багатьох)
CREATE TABLE core.resume_skills (
    resume_id INTEGER REFERENCES core.resumes(id) ON DELETE CASCADE,
    skill_id INTEGER REFERENCES dictionaries.skills(id) ON DELETE CASCADE,
    years_of_experience NUMERIC(4, 1), -- Досвід з конкретною технологією (напр. 1.5 роки)
    PRIMARY KEY (resume_id, skill_id)
);