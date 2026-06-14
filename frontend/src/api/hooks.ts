import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPatch } from './client'
import type {
  ActivityPoint,
  AdminStats,
  BucketSize,
  ClientPaginatedResumes,
  ClientPaginatedVacancies,
  ClientSearchFilters,
  CompanyStat,
  DataKind,
  EnglishLevelStat,
  ExperienceStat,
  ExperienceTimelinePoint,
  FailureRecord,
  LocationStat,
  Overview,
  PipelineStatus,
  SalaryBucket,
  SkillCategory,
  SkillGap,
  SkillStat,
  SourceStat,
  SystemMetrics,
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

export function useSources() {
  return useQuery({
    queryKey: ['sources'],
    queryFn: () => apiGet<SourceStat[]>('/api/analytics/sources'),
    staleTime: 5 * 60 * 1000,
  })
}

// ── Admin subsystem hooks ────────────────────────────────────────────────────

export function useAdminStats() {
  return useQuery({
    queryKey: ['admin-stats'],
    queryFn: () => apiGet<AdminStats>('/api/admin/stats'),
    staleTime: 30 * 1000,
  })
}

export function usePipelineStatus() {
  return useQuery({
    queryKey: ['admin-pipeline'],
    queryFn: () => apiGet<PipelineStatus>('/api/admin/pipeline/status'),
    staleTime: 30 * 1000,
  })
}

export function useSystemMetrics(enabled = true) {
  return useQuery({
    queryKey: ['admin-system'],
    queryFn: () => apiGet<SystemMetrics>('/api/admin/system'),
    enabled,
    staleTime: 15 * 1000,
    refetchInterval: 30 * 1000, // тримаємо «онлайн» актуальним
  })
}

export function useFailures(limit = 50) {
  return useQuery({
    queryKey: ['admin-failures', limit],
    queryFn: () => apiGet<FailureRecord[]>('/api/admin/failures', { limit }),
    staleTime: 30 * 1000,
  })
}

export function useResolveFailure() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      apiPatch<{ success: boolean }>(`/api/admin/failures/${id}/resolve`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['admin-failures'] })
      void qc.invalidateQueries({ queryKey: ['admin-pipeline'] })
    },
  })
}

// ── Client subsystem hooks ───────────────────────────────────────────────────

export function useClientVacancies(filters: ClientSearchFilters = {}) {
  return useQuery({
    queryKey: ['client-vacancies', filters],
    queryFn: () =>
      apiGet<ClientPaginatedVacancies>('/api/client/vacancies/search', { ...filters }),
    placeholderData: (prev) => prev,
  })
}

export function useClientResumes(filters: ClientSearchFilters = {}) {
  return useQuery({
    queryKey: ['client-resumes', filters],
    queryFn: () =>
      apiGet<ClientPaginatedResumes>('/api/client/resumes/search', { ...filters }),
    placeholderData: (prev) => prev,
  })
}
