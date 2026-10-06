import type {
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

// Oturum düşerse (süre doldu, başka sekmede çıkış) uygulama giriş ekranına döner
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
  register: (body: { name: string; email: string; password: string; organization_name: string; kvkk_onay: boolean }) =>
    post<Me>('/auth/register', body),
  logout: () => post<void>('/auth/logout'),
  saveProfile: (profile: OrgProfile) => request<Me>('/auth/profile', { method: 'PUT', body: JSON.stringify(profile) }),
  createNeed: (raw_text: string, organization?: { name: string; sector?: string; author_unit?: string; owner_unit?: string }) =>
    post<BriefOut>('/needs', { raw_text, organization }),
  listNeeds: () => request<NeedSummary[]>('/needs'),
  getBrief: (briefId: number) => request<BriefOut>(`/briefs/${briefId}`),
  answer: (briefId: number, answers: Record<string, string>) => post<BriefOut>(`/briefs/${briefId}/answers`, { answers }),
  runMatch: (briefId: number) => post<MatchOut>(`/briefs/${briefId}/match`),
  latestMatch: (briefId: number) => request<MatchView>(`/briefs/${briefId}/match`),
  decide: (matchId: number, decision: 'accept' | 'decline', reason?: string) =>
    post<{ match_id: number; status: string; pilot_id: number | null }>(`/matches/${matchId}/decision`, { decision, reason }),
  startups: () => request<StartupProfile[]>('/startups'),
  pilots: () => request<Pilot[]>('/pilots'),
  updatePilot: (pilotId: number, body: { status?: PilotStatus; outcome?: string; result?: PilotResult }) =>
    request<Pilot>(`/pilots/${pilotId}`, { method: 'PATCH', body: JSON.stringify(body) }),
  addMilestone: (pilotId: number, title: string, due_date?: string) =>
    post<Pilot>(`/pilots/${pilotId}/milestones`, { title, due_date: due_date || null }),
  completeMilestone: (milestoneId: number) => post<Pilot>(`/milestones/${milestoneId}/complete`),
}

// POST /match cevabını kayıtlı sonuç biçimine çevirir (yeni koşuda herkes "suggested")
export function toMatchView(out: MatchOut): MatchView {
  const withIds = (items: MatchOut['shortlist']) =>
    items.map((item) => ({ ...item, match_id: out.match_ids[item.startup.id], status: 'suggested' as const }))
  return { ...out, shortlist: withIds(out.shortlist), rejected: withIds(out.rejected) }
}
