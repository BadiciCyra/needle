import type {
  Claim,
  MetricInput,
  MilestoneOwner,
  NextStep,
  PilotDetail,
  PilotPlanInput,
  OrganizationCard,
  OrganizationRecommendations,
  StartupRecommendations,
  Report,
  Introduction,
  OpenCall,
  StartupProfileInput,
  BriefOut,
  Health,
  Me,
  OrgProfile,
  PilotResult,
  MatchOut,
  MatchView,
  NeedSummary,
  Pilot,
  PilotStatus,
  StartupProfile,
} from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(0, 'API’ye ulaşılamadı. Backend çalışıyor mu?')
  }
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* gövde JSON değil */
    }
    if (response.status === 401 && !path.startsWith('/auth/')) onUnauthorized?.()
    throw new ApiError(response.status, detail)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

let onUnauthorized: (() => void) | null = null
export const setUnauthorizedHandler = (handler: (() => void) | null) => {
  onUnauthorized = handler
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  health: () => request<Health>('/health'),
  me: () => request<Me>('/auth/me'),
  login: (email: string, password: string) => post<Me>('/auth/login', { email, password }),
  register: (body: RegisterBody) => post<Me>('/auth/register', body),
  logout: () => post<void>('/auth/logout'),
  requestPasswordReset: (email: string) => post<void>('/auth/password-reset/request', { email }),
  confirmPasswordReset: (token: string, password: string) => post<void>('/auth/password-reset/confirm', { token, password }),
  changePassword: (current_password: string, new_password: string) =>
    post<void>('/auth/password', { current_password, new_password }),
  saveProfile: (profile: OrgProfile) => request<Me>('/auth/profile', { method: 'PUT', body: JSON.stringify(profile) }),
  createNeed: (raw_text: string, organization?: { name: string; sector?: string; author_unit?: string; owner_unit?: string }) =>
    post<BriefOut>('/needs', { raw_text, organization }),
  listNeeds: () => request<NeedSummary[]>('/needs'),
  getBrief: (briefId: number) => request<BriefOut>(`/briefs/${briefId}`),
  answer: (briefId: number, answers: Record<string, string>) => post<BriefOut>(`/briefs/${briefId}/answers`, { answers }),
  runMatch: (briefId: number) => post<MatchOut>(`/briefs/${briefId}/match`),
  latestMatch: (briefId: number) => request<MatchView>(`/briefs/${briefId}/match`),
  decide: (matchId: number, decision: 'accept' | 'decline', reason?: string, note?: string) =>
    post<{ match_id: number; status: string; introduction_id: number | null }>(`/matches/${matchId}/decision`, {
      decision,
      reason,
      note,
    }),
  startups: () => request<StartupProfile[]>('/startups'),
  pilots: () => request<Pilot[]>('/pilots'),
  pilot: (pilotId: number) => request<PilotDetail>(`/pilots/${pilotId}`),
  updatePilot: (pilotId: number, body: { status?: PilotStatus; outcome?: string; result?: PilotResult }) =>
    request<PilotDetail>(`/pilots/${pilotId}`, { method: 'PATCH', body: JSON.stringify(body) }),
  updatePlan: (pilotId: number, body: PilotPlanInput) =>
    request<PilotDetail>(`/pilots/${pilotId}/plan`, { method: 'PATCH', body: JSON.stringify(body) }),
  fillPlanDefaults: (pilotId: number) => post<PilotDetail>(`/pilots/${pilotId}/plan/defaults`),
  addMilestone: (pilotId: number, title: string, due_date?: string, owner: MilestoneOwner = 'ortak') =>
    post<PilotDetail>(`/pilots/${pilotId}/milestones`, { title, due_date: due_date || null, owner }),
  editMilestone: (milestoneId: number, body: { title?: string; due_date?: string | null; owner?: MilestoneOwner }) =>
    request<PilotDetail>(`/milestones/${milestoneId}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteMilestone: (milestoneId: number) => request<PilotDetail>(`/milestones/${milestoneId}`, { method: 'DELETE' }),
  completeMilestone: (milestoneId: number) => post<PilotDetail>(`/milestones/${milestoneId}/complete`),
  reopenMilestone: (milestoneId: number) => post<PilotDetail>(`/milestones/${milestoneId}/reopen`),
  addMetric: (pilotId: number, body: MetricInput) => post<PilotDetail>(`/pilots/${pilotId}/metrics`, body),
  editMetric: (metricId: number, body: MetricInput) =>
    request<PilotDetail>(`/metrics/${metricId}`, { method: 'PATCH', body: JSON.stringify(body) }),
  deleteMetric: (metricId: number) => request<PilotDetail>(`/metrics/${metricId}`, { method: 'DELETE' }),
  addMeasurement: (metricId: number, value: number, measured_on?: string, note?: string) =>
    post<PilotDetail>(`/metrics/${metricId}/measurements`, { value, measured_on: measured_on || null, note: note || null }),
  deleteMeasurement: (measurementId: number) => request<PilotDetail>(`/measurements/${measurementId}`, { method: 'DELETE' }),
  addNote: (pilotId: number, body: string) => post<PilotDetail>(`/pilots/${pilotId}/activity`, { body }),
  evaluatePilot: (pilotId: number, body: { result: PilotResult; next_step: NextStep; startup_rating: number; comment?: string }) =>
    post<PilotDetail>(`/pilots/${pilotId}/evaluation`, body),
  startupFeedback: (pilotId: number, body: { feedback: string; collab_rating: number | null }) =>
    post<PilotDetail>(`/pilots/${pilotId}/startup-feedback`, body),

  claimStartup: (startup_id: string) => post<Me>('/startup-account/claim', { startup_id }),
  createStartupProfile: (profile: StartupProfileInput) => post<Me>('/startup-account/new', profile),
  myStartupProfile: () => request<StartupProfile>('/startup-account/profile'),
  updateStartupProfile: (profile: StartupProfileInput) =>
    request<StartupProfile>('/startup-account/profile', { method: 'PUT', body: JSON.stringify(profile) }),

  claims: () => request<Claim[]>('/admin/claims'),
  approveClaim: (userId: number) => post<void>(`/admin/claims/${userId}/approve`),
  rejectClaim: (userId: number) => post<void>(`/admin/claims/${userId}/reject`),

  organizations: () => request<OrganizationCard[]>('/organizations'),
  startupRecommendations: () => request<StartupRecommendations>('/startup-account/recommendations'),
  organizationRecommendations: () => request<OrganizationRecommendations>('/organization/recommendations'),

  report: () => request<Report>('/admin/report'),

  introductions: () => request<Introduction[]>('/introductions'),
  respondIntroduction: (id: number, decision: 'kabul' | 'ret', note?: string) =>
    post<Introduction>(`/introductions/${id}/respond`, { decision, note }),
  createIntroEmail: (id: number) => post<Introduction>(`/introductions/${id}/email/draft`),
  saveIntroEmail: (id: number, body: { to: string | null; subject: string; body: string }) =>
    request<Introduction>(`/introductions/${id}/email`, { method: 'PUT', body: JSON.stringify(body) }),
  markIntroEmailSent: (id: number, sent: boolean) => post<Introduction>(`/introductions/${id}/email/sent`, { sent }),

  calls: () => request<OpenCall[]>('/calls'),
  call: (id: number) => request<OpenCall>(`/calls/${id}`),
  createCall: (body: { brief_id: number; title: string; summary: string; hide_organization: boolean; deadline: string | null }) =>
    post<OpenCall>('/calls', body),
  setCallStatus: (id: number, status: 'acik' | 'kapali') =>
    request<OpenCall>(`/calls/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  apply: (callId: number, note: string) => post<OpenCall>(`/calls/${callId}/applications`, { note }),
  decideApplication: (applicationId: number, decision: 'kabul' | 'ret', note?: string) =>
    post<OpenCall>(`/applications/${applicationId}/decision`, { decision, note }),
}

export interface RegisterBody {
  name: string
  email: string
  password: string
  account_type: 'firma' | 'girisim'
  organization_name: string | null
  kvkk_onay: boolean
}

export function toMatchView(out: MatchOut): MatchView {
  const withIds = (items: MatchOut['shortlist']) =>
    items.map((item) => ({ ...item, match_id: out.match_ids[item.startup.id], status: 'suggested' as const }))
  return { ...out, shortlist: withIds(out.shortlist), rejected: withIds(out.rejected) }
}
