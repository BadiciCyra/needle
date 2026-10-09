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
  examples?: string[]
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
  website?: string | null
}

export interface EvidenceLink {
  brief_phrase: string
  startup_capability: string
  explanation: string
  support_score?: number | null
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
  introduction?: Introduction | null
}

export interface MatchView {
  brief_id: number
  run_id: number
  shortlist: MatchItem[]
  rejected: MatchItem[]
  retrieval_trace: string[]
  trace_steps?: TraceStep[]
  open_call_id?: number | null
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

export type MilestoneOwner = 'kurum' | 'girisim' | 'ortak'

export interface Milestone {
  id: number
  title: string
  due_date: string | null
  completed_at: string | null
  owner: MilestoneOwner
  overdue: boolean
}

export type PilotStatus = 'active' | 'paused' | 'done' | 'cancelled'
export type PilotResult = 'evet' | 'kismen' | 'hayir'

export interface Pilot {
  id: number
  status: PilotStatus
  match_id: number | null
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
  start_date: string | null
  end_date: string | null
  overdue_milestones: number
  next_step: NextStep | null
  evaluated_at: string | null
}

export type NextStep = 'satin_alma' | 'genisletme' | 'yeni_pilot' | 'bitir'

export interface Measurement {
  id: number
  value: number
  measured_on: string
  note: string | null
  author_role: string
}

export interface Metric {
  id: number
  name: string
  unit: string | null
  baseline: number | null
  target: number | null
  direction: 'artis' | 'azalis'
  latest: number | null
  progress: number | null
  achieved: boolean | null
  measurements: Measurement[]
}

export interface Activity {
  id: number
  kind: 'not' | 'olay'
  author_role: string
  author_name: string | null
  body: string
  created_at: string
}

export interface PilotDetail extends Pilot {
  goal: string | null
  scope: string | null
  firm_contact: string | null
  startup_contact: string | null
  startup_rating: number | null
  startup_feedback: string | null
  collab_rating: number | null
  startup_feedback_at: string | null
  metrics: Metric[]
  activity: Activity[]
}

export interface PilotPlanInput {
  goal?: string | null
  scope?: string | null
  start_date?: string | null
  end_date?: string | null
  firm_contact?: string | null
  startup_contact?: string | null
}

export interface MetricInput {
  name: string
  unit: string | null
  baseline: number | null
  target: number | null
  direction: 'artis' | 'azalis'
}

export interface Health {
  status: string
  llm_model: string
  demo_mode: string
  rerank_backend: string
}

export type Role = 'firma' | 'yonetici' | 'girisim'

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
  description?: string | null
  website?: string | null
  directory_visible?: boolean
}

export interface OrganizationCard {
  id: number
  name: string
  sector: string | null
  city: string | null
  employee_range: string | null
  description: string | null
  website: string | null
  open_calls: { id: number; title: string; deadline: string | null }[]
  joined_at: string | null
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
  startup: StartupAccount | null
}

export interface StartupAccount {
  id: string
  name: string
  status: 'aktif' | 'onay_bekliyor' | 'reddedildi'
  verified: boolean
}

export interface StartupProfileInput {
  name: string
  sector: string
  maturity: Maturity
  location: string
  website: string | null
  description: string
  capabilities: string[]
  past_pilots: string[]
}

export type IntroStatus = 'bekliyor' | 'kabul' | 'ret'

export interface Introduction {
  id: number
  status: IntroStatus
  brief_id: number
  brief: {
    title: string
    problem: string | null
    scope: string | null
    required_capabilities: string[]
    success_criteria: string | null
    timeline: string | null
  }
  organization: string | null
  startup: StartupProfile
  startup_has_account: boolean
  source: 'eslestirme' | 'cagri'
  firm_note: string | null
  startup_note: string | null
  responded_by: 'girisim' | 'yonetici' | null
  created_at: string
  responded_at: string | null
  pilot_id: number | null
  email?: IntroEmail | null
}

export interface IntroEmail {
  to: string | null
  subject: string
  body: string
  contact_source: string | null
  updated_at: string | null
  sent_at: string | null
}

export interface Application {
  id: number
  call_id: number
  startup: StartupProfile
  note: string
  status: 'yeni' | 'kabul' | 'ret'
  decision_note: string | null
  created_at: string
  pilot_id: number | null
}

export interface OpenCall {
  id: number
  brief_id: number
  title: string
  summary: string
  organization: string | null
  sector: string | null
  required_capabilities: string[]
  deadline: string | null
  status: 'acik' | 'kapali'
  created_at: string
  hide_organization: boolean
  application_count: number
  my_application: Application | null
  applications: Application[]
}

export interface Claim {
  user_id: number
  user_name: string
  email: string
  startup: StartupProfile
  startup_status: string
  kind: 'sahiplenme' | 'yeni_profil'
  domain_match: boolean
  created_at: string
}

export interface Report {
  generated_at: string
  funnel: { needs: number; briefed: number; matched: number; no_match: number; introduced: number; piloted: number; worked: number }
  introductions: {
    total: number
    waiting: number
    accepted: number
    declined: number
    acceptance_rate: number | null
    avg_response_days: number | null
    via_admin: number
  }
  pilots: { total: number; active: number; stale: number; done: number; result_evet: number; result_kismen: number; result_hayir: number }
  sectors: { sector: string; needs: number; no_match: number; introduced: number; pilots: number; worked: number }[]
  missing_capabilities: { capability: string; needs: number; variants: string[]; need_titles: string[] }[]
  unmet_needs: {
    brief_id: number
    title: string
    organization: string | null
    sector: string
    required_capabilities: string[]
    open_call_id: number | null
    applications: number
  }[]
  pool: { sector: string; startups: number; with_account: number }[]
  open_calls: number
  applications: number
}
