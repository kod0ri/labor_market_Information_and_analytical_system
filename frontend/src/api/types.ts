export interface Overview {
  total_vacancies: number
  total_resumes: number
  vacancies_with_salary: number
  resumes_with_salary: number
  avg_vacancy_salary_usd: number | null
  avg_resume_salary_usd: number | null
}

export interface SnapshotItem {
  snapshot_date: string
  category: string
  total_vacancies: number
  total_resumes: number
  avg_vacancy_salary_usd: number | null
  avg_resume_salary_usd: number | null
}

export type SkillCategory = 'Hard' | 'Soft'
export type DataKind = 'vacancy' | 'resume'

export interface SkillStat {
  name: string
  category: SkillCategory | string
  count: number
}

export interface SkillGap {
  name: string
  category: string
  vacancy_count: number
  resume_count: number
  gap: number
}

export interface LocationStat {
  city_name: string
  region: string | null
  count: number
}

export interface SalaryBucket {
  range_label: string
  min_usd: number | null
  max_usd: number | null
  count: number
}

export interface EnglishLevelStat {
  level: string | null
  count: number
}

export interface ExperienceStat {
  bucket: string
  sort_key: number
  count: number
  avg_salary_usd: number | null
}

export interface CompanyStat {
  name: string
  count: number
}

export interface SourceStat {
  source: string
  vacancies: number
  resumes: number
}

export type BucketSize = 'day' | 'week' | 'month'

export interface ActivityPoint {
  bucket_start: string
  new_vacancies: number
  new_resumes: number
  avg_vacancy_salary_usd: number | null
  avg_resume_salary_usd: number | null
}

export interface ExperienceTimelinePoint {
  bucket_start: string
  junior: number
  middle: number
  senior: number
  unknown: number
}

export interface Vacancy {
  id: number
  title: string
  company_name: string | null
  city_name: string | null
  region: string | null
  min_salary_usd_eq: number | null
  max_salary_usd_eq: number | null
  experience_years: number | null
  english_level: string | null
  created_at: string
  skills: string[]
}

export interface Resume {
  id: number
  title: string
  city_name: string | null
  region: string | null
  min_salary_usd_eq: number | null
  max_salary_usd_eq: number | null
  experience_years: number | null
  english_level: string | null
  created_at: string
  skills: string[]
}

// ── Admin subsystem ──────────────────────────────────────────────────────────

export interface AdminStats {
  processed: { vacancies: number; resumes: number }
  dictionaries: { skills: number; companies: number; locations: number }
  pipeline_queue: { vacancies_pending: number; resumes_pending: number }
}

export interface PipelineStatus {
  queue: { vacancies_pending: number; resumes_pending: number }
  failures: { total_unresolved: number; by_type: Record<string, number> }
  last_processed: { vacancy_at: string | null; resume_at: string | null }
}

export interface FailureRecord {
  id: number
  record_type: string
  staging_id: number
  error_type: string
  error_detail: string
  attempt_count: number
  is_resolved: boolean
  failed_at: string | null
}

export interface SystemUser {
  id: number
  username: string
  is_active: boolean
  is_online: boolean
  created_at: string | null
  last_seen_at: string | null
}

export interface SystemMetrics {
  visitors: {
    online: number
    last_24h: number
    last_7d: number
    avg_online_24h: number
    peak_online_24h: number
  }
  users: {
    total: number
    active: number
    online: number
    new_7d: number
    list: SystemUser[]
  }
  server: {
    uptime_seconds: number
    disk: {
      path: string
      total_bytes: number
      used_bytes: number
      free_bytes: number
      used_percent: number
    }
    memory: {
      total_bytes: number
      used_bytes: number
      available_bytes: number
      used_percent: number
    } | null
    load_average: { '1m': number; '5m': number; '15m': number } | null
    database_size_bytes: number
    cpu_count: number | null
  }
}

// ── Client subsystem ─────────────────────────────────────────────────────────

export interface ClientSearchFilters {
  page?: number
  page_size?: number
  skill?: string
  location?: string
  min_salary_usd?: number
  experience_max?: number
  experience_min?: number
  english_level?: string
  source?: string
}

export interface ClientPaginatedVacancies {
  items: Vacancy[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface ClientPaginatedResumes {
  items: Resume[]
  total: number
  page: number
  page_size: number
  pages: number
}
