import { useQuery } from '@tanstack/react-query'
import { apiGet } from './client'
import type {
  ActivityPoint,
  BucketSize,
  CompanyStat,
  DataKind,
  EnglishLevelStat,
  ExperienceStat,
  ExperienceTimelinePoint,
  LocationStat,
  Overview,
  PaginatedResumes,
  PaginatedVacancies,
  ResumeFilters,
  SalaryBucket,
  SkillCategory,
  SkillGap,
  SkillStat,
  VacancyFilters,
} from './types'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<{ status: string; database: string }>('/health'),
    staleTime: 60 * 1000,
    retry: 0,
  })
}

export function useOverview() {
  return useQuery({
    queryKey: ['overview'],
    queryFn: () => apiGet<Overview>('/api/analytics/overview'),
    staleTime: 5 * 60 * 1000,
  })
}

export function useTopSkills(
  type: DataKind = 'vacancy',
  limit = 20,
  category?: SkillCategory,
) {
  return useQuery({
    queryKey: ['skills', type, limit, category],
    queryFn: () =>
      apiGet<SkillStat[]>('/api/analytics/skills', { type, limit, category }),
  })
}

export function useSkillGap(limit = 20) {
  return useQuery({
    queryKey: ['skills-gap', limit],
    queryFn: () => apiGet<SkillGap[]>('/api/analytics/skills/gap', { limit }),
  })
}

export function useLocations(type: DataKind = 'vacancy', limit = 10) {
  return useQuery({
    queryKey: ['locations', type, limit],
    queryFn: () =>
      apiGet<LocationStat[]>('/api/analytics/locations', { type, limit }),
  })
}

export function useSalaryDistribution(type: DataKind = 'vacancy') {
  return useQuery({
    queryKey: ['salary-distribution', type],
    queryFn: () =>
      apiGet<SalaryBucket[]>('/api/analytics/salary-distribution', { type }),
  })
}

export function useVacancies(filters: VacancyFilters = {}) {
  return useQuery({
    queryKey: ['vacancies', filters],
    queryFn: () =>
      apiGet<PaginatedVacancies>('/api/vacancies/', { ...filters }),
    placeholderData: (prev) => prev,
  })
}

export function useEnglishLevels(type: DataKind = 'vacancy') {
  return useQuery({
    queryKey: ['english-levels', type],
    queryFn: () =>
      apiGet<EnglishLevelStat[]>('/api/analytics/english-levels', { type }),
  })
}

export function useExperienceLevels(type: DataKind = 'vacancy') {
  return useQuery({
    queryKey: ['experience-levels', type],
    queryFn: () =>
      apiGet<ExperienceStat[]>('/api/analytics/experience-levels', { type }),
  })
}

export function useActivity(bucket: BucketSize = 'week', days = 90) {
  return useQuery({
    queryKey: ['activity', bucket, days],
    queryFn: () =>
      apiGet<ActivityPoint[]>('/api/analytics/activity', { bucket, days }),
  })
}

export function useExperienceTimeline(
  type: DataKind = 'vacancy',
  bucket: BucketSize = 'week',
  days = 90,
) {
  return useQuery({
    queryKey: ['experience-timeline', type, bucket, days],
    queryFn: () =>
      apiGet<ExperienceTimelinePoint[]>('/api/analytics/experience-timeline', {
        type,
        bucket,
        days,
      }),
  })
}

export function useTopCompanies(limit = 10) {
  return useQuery({
    queryKey: ['companies', limit],
    queryFn: () => apiGet<CompanyStat[]>('/api/analytics/companies', { limit }),
  })
}

export function useResumes(filters: ResumeFilters = {}) {
  return useQuery({
    queryKey: ['resumes', filters],
    queryFn: () =>
      apiGet<PaginatedResumes>('/api/resumes/', { ...filters }),
    placeholderData: (prev) => prev,
  })
}
