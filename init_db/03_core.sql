-- Таблиця вакансій
CREATE TABLE core.vacancies (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    staging_id INTEGER REFERENCES staging.raw_vacancies(id),
    title VARCHAR(255) NOT NULL,
    company_id INTEGER REFERENCES dictionaries.companies(id),
    location_id INTEGER REFERENCES dictionaries.locations(id),
    source_id INTEGER REFERENCES dictionaries.sources(id),
    min_salary NUMERIC,
    max_salary NUMERIC,
    currency VARCHAR(10),
    min_salary_usd_eq NUMERIC,
    max_salary_usd_eq NUMERIC,
    experience_years INTEGER,
    english_level VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблиця резюме
CREATE TABLE core.resumes (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    staging_id INTEGER REFERENCES staging.raw_resumes(id),
    title VARCHAR(255) NOT NULL,
    location_id INTEGER REFERENCES dictionaries.locations(id),
    source_id INTEGER REFERENCES dictionaries.sources(id),
    min_salary NUMERIC,
    max_salary NUMERIC,
    currency VARCHAR(10),
    min_salary_usd_eq NUMERIC,
    max_salary_usd_eq NUMERIC,
    experience_years INTEGER,
    english_level VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Зв'язок: Які навички вимагаються у вакансії (Багато-до-Багатьох)
CREATE TABLE core.vacancy_skills (
    vacancy_id INTEGER REFERENCES core.vacancies(id) ON DELETE CASCADE,
    skill_id INTEGER REFERENCES dictionaries.skills(id) ON DELETE CASCADE,
    PRIMARY KEY (vacancy_id, skill_id)
);

-- Зв'язок: Які навички має кандидат (Багато-до-Багатьох)
CREATE TABLE core.resume_skills (
    resume_id INTEGER REFERENCES core.resumes(id) ON DELETE CASCADE,
    skill_id INTEGER REFERENCES dictionaries.skills(id) ON DELETE CASCADE,
    PRIMARY KEY (resume_id, skill_id)
);

-- Індекси для таблиці вакансій
CREATE INDEX idx_vacancies_company_id ON core.vacancies(company_id);
CREATE INDEX idx_vacancies_location_id ON core.vacancies(location_id);
CREATE INDEX idx_vacancies_created_at ON core.vacancies(created_at);

-- Індекси для таблиці резюме
CREATE INDEX idx_resumes_location_id ON core.resumes(location_id);
CREATE INDEX idx_resumes_created_at ON core.resumes(created_at);

CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER trigger_update_vacancies
    BEFORE UPDATE ON core.vacancies
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER trigger_update_resumes
    BEFORE UPDATE ON core.resumes
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();
