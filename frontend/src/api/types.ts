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

export interface PaginatedVacancies {
  total: number
  page: number
  limit: number
  items: Vacancy[]
}

export interface VacancyFilters {
  page?: number
  limit?: number
  skill?: string
  location?: string
  min_salary_usd?: number
  experience_years?: number
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

export interface PaginatedResumes {
  total: number
  page: number
  limit: number
  items: Resume[]
}

export type ResumeFilters = VacancyFilters
