-- =============================================================================
-- Міграція: нормалізація навичок
-- Файл: init_db/05_skill_normalization.sql
--
-- Що робимо:
-- 1. Додаємо UNIQUE constraint на name (case-insensitive) через функціональний індекс
-- 2. Заповнюємо базові синоніми для найпоширеніших IT-навичок
-- 3. Нормалізуємо існуючі записи в dictionaries.skills до canonical form
-- =============================================================================

-- -----------------------------------------------------------------------
-- Крок 1: Функціональний унікальний індекс — не дає вставити 'python' і 'Python'
-- як дві різні навички. Стандартний UNIQUE (name) цього не ловить.
-- -----------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS idx_skills_name_lower
    ON dictionaries.skills (LOWER(name));

-- -----------------------------------------------------------------------
-- Крок 2: Базовий словник синонімів
-- Формат: (canonical_name, synonym)
-- canonical_name — як навичка МАЄ виглядати в БД
-- synonym — що LLM може повернути замість неї
-- -----------------------------------------------------------------------
DO $$
DECLARE
    skill_id INTEGER;
BEGIN

    -- ===== Мови програмування =====

    INSERT INTO dictionaries.skills (name, category) VALUES ('Python', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Python';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'python'),
        (skill_id, 'Python3'),
        (skill_id, 'python3'),
        (skill_id, 'Python 3'),
        (skill_id, 'py')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('JavaScript', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'JavaScript';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'javascript'),
        (skill_id, 'JS'),
        (skill_id, 'js'),
        (skill_id, 'Java Script'),
        (skill_id, 'ECMAScript'),
        (skill_id, 'ES6'),
        (skill_id, 'ES2015')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('TypeScript', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'TypeScript';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'typescript'),
        (skill_id, 'TS'),
        (skill_id, 'ts')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Java', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Java';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'java'),
        (skill_id, 'Core Java'),
        (skill_id, 'Java SE'),
        (skill_id, 'Java EE')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('C#', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'C#';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'c#'),
        (skill_id, 'CSharp'),
        (skill_id, 'csharp'),
        (skill_id, 'C Sharp')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('C++', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'C++';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'c++'),
        (skill_id, 'CPP'),
        (skill_id, 'cpp')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Go', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Go';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'go'),
        (skill_id, 'Golang'),
        (skill_id, 'golang')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Rust', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Rust';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'rust'),
        (skill_id, 'Rust lang'),
        (skill_id, 'rust-lang')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('PHP', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'PHP';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'php'),
        (skill_id, 'PHP8'),
        (skill_id, 'PHP 8')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Ruby', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Ruby';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'ruby'),
        (skill_id, 'Ruby lang')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Kotlin', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Kotlin';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'kotlin')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Swift', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Swift';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'swift')
    ON CONFLICT (synonym) DO NOTHING;

    -- ===== Фреймворки / бібліотеки =====

    INSERT INTO dictionaries.skills (name, category) VALUES ('Django', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Django';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'django'),
        (skill_id, 'Django REST'),
        (skill_id, 'Django REST Framework'),
        (skill_id, 'DRF')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('FastAPI', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'FastAPI';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'fastapi'),
        (skill_id, 'Fast API')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Flask', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Flask';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'flask')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('React', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'React';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'react'),
        (skill_id, 'ReactJS'),
        (skill_id, 'reactjs'),
        (skill_id, 'React.js'),
        (skill_id, 'react.js')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Vue.js', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Vue.js';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'vue.js'),
        (skill_id, 'Vue'),
        (skill_id, 'vue'),
        (skill_id, 'VueJS'),
        (skill_id, 'vuejs')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Angular', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Angular';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'angular'),
        (skill_id, 'AngularJS'),
        (skill_id, 'angularjs')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Node.js', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Node.js';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'node.js'),
        (skill_id, 'NodeJS'),
        (skill_id, 'nodejs'),
        (skill_id, 'Node')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Spring Boot', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Spring Boot';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'spring boot'),
        (skill_id, 'Spring'),
        (skill_id, 'spring'),
        (skill_id, 'Spring Framework')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Ruby on Rails', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Ruby on Rails';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'ruby on rails'),
        (skill_id, 'Rails'),
        (skill_id, 'rails'),
        (skill_id, 'RoR'),
        (skill_id, 'ror')
    ON CONFLICT (synonym) DO NOTHING;

    -- ===== Бази даних =====

    INSERT INTO dictionaries.skills (name, category) VALUES ('PostgreSQL', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'PostgreSQL';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'postgresql'),
        (skill_id, 'Postgres'),
        (skill_id, 'postgres'),
        (skill_id, 'PG'),
        (skill_id, 'pg')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('MySQL', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'MySQL';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'mysql'),
        (skill_id, 'My SQL')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('MongoDB', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'MongoDB';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'mongodb'),
        (skill_id, 'Mongo'),
        (skill_id, 'mongo')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Redis', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Redis';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'redis')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Elasticsearch', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Elasticsearch';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'elasticsearch'),
        (skill_id, 'Elastic Search'),
        (skill_id, 'ES')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('SQLite', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'SQLite';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'sqlite')
    ON CONFLICT (synonym) DO NOTHING;

    -- ===== DevOps / Інфраструктура =====

    INSERT INTO dictionaries.skills (name, category) VALUES ('Docker', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Docker';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'docker'),
        (skill_id, 'Docker Compose'),
        (skill_id, 'docker-compose')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Kubernetes', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Kubernetes';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'kubernetes'),
        (skill_id, 'K8s'),
        (skill_id, 'k8s')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('AWS', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'AWS';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'aws'),
        (skill_id, 'Amazon Web Services'),
        (skill_id, 'Amazon AWS')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('GCP', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'GCP';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'gcp'),
        (skill_id, 'Google Cloud'),
        (skill_id, 'Google Cloud Platform')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Azure', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Azure';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'azure'),
        (skill_id, 'Microsoft Azure')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('CI/CD', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'CI/CD';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'ci/cd'),
        (skill_id, 'GitLab CI'),
        (skill_id, 'GitHub Actions'),
        (skill_id, 'Jenkins'),
        (skill_id, 'CircleCI')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Linux', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Linux';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'linux'),
        (skill_id, 'Ubuntu'),
        (skill_id, 'unix'),
        (skill_id, 'Unix')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Git', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Git';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'git'),
        (skill_id, 'GitHub'),
        (skill_id, 'GitLab'),
        (skill_id, 'Bitbucket')
    ON CONFLICT (synonym) DO NOTHING;

    -- ===== Data / ML =====

    INSERT INTO dictionaries.skills (name, category) VALUES ('SQL', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'SQL';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'sql'),
        (skill_id, 'T-SQL'),
        (skill_id, 'PL/SQL'),
        (skill_id, 'PL-SQL')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Pandas', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Pandas';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'pandas')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('NumPy', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'NumPy';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'numpy'),
        (skill_id, 'Numpy')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('TensorFlow', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'TensorFlow';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'tensorflow'),
        (skill_id, 'TF')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('PyTorch', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'PyTorch';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'pytorch'),
        (skill_id, 'Torch')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Apache Kafka', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Apache Kafka';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'apache kafka'),
        (skill_id, 'Kafka'),
        (skill_id, 'kafka')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Apache Spark', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Apache Spark';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'apache spark'),
        (skill_id, 'Spark'),
        (skill_id, 'spark'),
        (skill_id, 'PySpark'),
        (skill_id, 'pyspark')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Airflow', 'Hard')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Airflow';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'airflow'),
        (skill_id, 'Apache Airflow')
    ON CONFLICT (synonym) DO NOTHING;

    -- ===== Soft Skills =====

    INSERT INTO dictionaries.skills (name, category) VALUES ('Teamwork', 'Soft')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Teamwork';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'teamwork'),
        (skill_id, 'Team player'),
        (skill_id, 'team player'),
        (skill_id, 'Робота в команді')
    ON CONFLICT (synonym) DO NOTHING;

    INSERT INTO dictionaries.skills (name, category) VALUES ('Communication', 'Soft')
        ON CONFLICT (name) DO NOTHING;
    SELECT id INTO skill_id FROM dictionaries.skills WHERE name = 'Communication';
    INSERT INTO dictionaries.skill_synonyms (skill_id, synonym) VALUES
        (skill_id, 'communication'),
        (skill_id, 'Комунікація'),
        (skill_id, 'Комунікабельність')
    ON CONFLICT (synonym) DO NOTHING;

END;
$$;