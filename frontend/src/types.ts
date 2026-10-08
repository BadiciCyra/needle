// Backend şemalarının (backend/app/schemas.py, backend/app/api/schemas.py) TypeScript karşılıkları

export type Maturity = 'fikir' | 'prototip' | 'mvp' | 'ilk_gelir' | 'buyume'

export interface Brief {
  title: string
  problem: string | null
  scope: string | null
  required_capabilities: string[]
  sector: string | null
  success_criteria: string | null
  timeline: string | null
  budget: string | null
  location_preference: string | null
  min_maturity: Maturity | null
  missing_fields: string[]
}

export interface FollowUpQuestion {
  field: string
  question: string
  examples?: string[] // tek dokunuşla seçilebilen hazır cevaplar
}

export interface BriefOut {
  brief_id: number
  need_id: number
  status: 'needs_input' | 'final'
  brief: Brief
  questions: FollowUpQuestion[]
}

export interface StartupProfile {
  id: string
  name: string
  sector: string
  maturity: Maturity
  location: string
  capabilities: string[]
  description: string
  past_pilots: string[]
}

export interface EvidenceLink {
  brief_phrase: string
  startup_capability: string
  explanation: string
  support_score?: number | null // ifade–yetkinlik benzerliği (0-1), kod hesaplar
}

export interface MatchRationale {
  startup_id: string
  fit_summary: string
  evidence: EvidenceLink[]
}

export interface RejectionRationale {
  startup_id: string
  near_miss_reason: string
  missing_capability: string | null
}

export type MatchStatus = 'suggested' | 'accepted' | 'declined'

export interface MatchItem {
  rank: number
  startup: StartupProfile
  score: number
  vector_score: number
  rationale: MatchRationale | null
  rejection: RejectionRationale | null
  filter_notes: string[]
  match_id: number
  status: MatchStatus
  declined_reason?: string | null
}

export interface MatchView {
  brief_id: number
  run_id: number
  shortlist: MatchItem[]
  rejected: MatchItem[]
  retrieval_trace: string[]
  trace_steps?: TraceStep[] // eski kayıtlarda boş
}

export interface TraceStep {
  stage: 'plan' | 'retrieve' | 'relax' | 'rerank' | 'threshold' | 'evidence'
  message: string
  round?: number
  filters?: string
  queries?: number
  new_candidates?: number
  pool_size?: number
  candidates?: number
  indirect?: number
  shortlist_size?: number
  rejected_size?: number
  evidence_kept?: number
  evidence_total?: number
}

// POST /briefs/{id}/match cevabı: durumlar ayrı bir sözlükte gelir
export interface MatchOut extends Omit<MatchView, 'shortlist' | 'rejected'> {
  shortlist: Omit<MatchItem, 'match_id' | 'status'>[]
  rejected: Omit<MatchItem, 'match_id' | 'status'>[]
  match_ids: Record<string, number>
}

export interface NeedSummary {
  brief_id: number
  need_id: number
  title: string
  status: 'needs_input' | 'final'
  raw_text: string
  organization: string | null
  created_at: string
  shortlist_count: number
  accepted_count: number
}

export interface Milestone {
  id: number
  title: string
  due_date: string | null
  completed_at: string | null
}

export type PilotStatus = 'active' | 'paused' | 'done' | 'cancelled'
export type PilotResult = 'evet' | 'kismen' | 'hayir'

export interface Pilot {
  id: number
  status: PilotStatus
  match_id: number
  brief_id: number
  brief_title: string
  startup: StartupProfile
  started_at: string
  last_activity_at: string
  days_inactive: number
  stale: boolean
  outcome: string | null
  result: PilotResult | null
  milestones: Milestone[]
  organization: string | null
}

export interface Health {
  status: string
  llm_model: string
  demo_mode: string
  rerank_backend: string
}

// Hesaplar ve firma profili (backend/app/api/schemas.py)
export type Role = 'firma' | 'yonetici'

export interface OrgProfile {
  sector: string
  city: string
  employee_range: '1-49' | '50-249' | '250-999' | '1000+'
  systems: string[]
  preferred_maturity: Maturity | null
  startup_location: 'ayni_sehir' | 'fark_etmez'
  budget_range: string | null
  pilot_duration: string | null
  data_constraints: string[]
}

export interface Me {
  id: number
  name: string
  email: string
  role: Role
  organization: {
    id: number
    name: string
    sector: string | null
    profile: Partial<OrgProfile>
    onboarded: boolean
  } | null
}
