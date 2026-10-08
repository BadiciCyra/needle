import type { ComboboxItem, OptionsFilter } from '@mantine/core'

import type { IntroStatus, Maturity, NeedSummary, PilotResult, PilotStatus } from './types'

export const MATURITY_LABEL: Record<Maturity, string> = {
  fikir: 'Fikir',
  prototip: 'Prototip',
  mvp: 'MVP',
  ilk_gelir: 'İlk gelir',
  buyume: 'Büyüme',
}

export const MATURITY_ORDER: Maturity[] = ['fikir', 'prototip', 'mvp', 'ilk_gelir', 'buyume']

// Etiket renkleri: kare işaretin rengi (CSS değeri)
export const TAG_COLOR = {
  green: '#3f7a52',
  ochre: '#c08a2a',
  slate: '#5b7186',
  thread: 'var(--mantine-color-thread-6)',
  ink: 'var(--app-ink)',
  gray: '#a29e95',
  red: 'var(--app-danger)',
}

export const PILOT_STATUS: Record<PilotStatus, { label: string; color: string }> = {
  active: { label: 'Aktif', color: TAG_COLOR.green },
  paused: { label: 'Duraklatıldı', color: TAG_COLOR.ochre },
  done: { label: 'Tamamlandı', color: TAG_COLOR.ink },
  cancelled: { label: 'İptal edildi', color: TAG_COLOR.gray },
}

export const INTRO_STATUS: Record<IntroStatus, { label: string; color: string }> = {
  bekliyor: { label: 'Girişimin cevabı bekleniyor', color: TAG_COLOR.ochre },
  kabul: { label: 'Tanıştırma kabul edildi', color: TAG_COLOR.green },
  ret: { label: 'Girişim reddetti', color: TAG_COLOR.gray },
}

export const PILOT_RESULT: Record<PilotResult, string> = { evet: 'Evet', kismen: 'Kısmen', hayir: 'Hayır' }

// İhtiyacın süreçteki aşaması (NeedSummary'den türetilir)
export type Stage = 'followup' | 'ready' | 'review' | 'pilot'

export const STAGE: Record<Stage, { label: string; color: string; hint: string }> = {
  followup: { label: 'Bilgi bekliyor', color: TAG_COLOR.ochre, hint: 'Takip sorularının cevaplanması gerekiyor' },
  ready: { label: 'Eşleştirmeye hazır', color: TAG_COLOR.slate, hint: 'Brief tamam, aday aranmadı' },
  review: { label: 'Karar bekliyor', color: TAG_COLOR.thread, hint: 'Kısa liste hazır, kabul/ret bekleniyor' },
  pilot: { label: 'Aday seçildi', color: TAG_COLOR.green, hint: 'En az bir adaya tanıştırma isteği gönderildi' },
}

export function stageOf(need: NeedSummary): Stage {
  if (need.status === 'needs_input') return 'followup'
  if (need.accepted_count > 0) return 'pilot'
  if (need.shortlist_count > 0) return 'review'
  return 'ready'
}

export const BRIEF_FIELD_LABEL: Record<string, string> = {
  title: 'Başlık',
  problem: 'Problem',
  scope: 'Kapsam',
  required_capabilities: 'Gereken yetkinlikler',
  sector: 'Sektör',
  success_criteria: 'Başarı kriteri',
  timeline: 'Süre',
  budget: 'Bütçe',
  location_preference: 'Lokasyon tercihi',
  min_maturity: 'En düşük olgunluk',
}

export const formatDate = (value: string | null) =>
  value ? new Date(value).toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

const rtf = new Intl.RelativeTimeFormat('tr', { numeric: 'auto' })

export function timeAgo(value: string) {
  const days = Math.round((new Date(value).getTime() - Date.now()) / 86_400_000)
  if (Math.abs(days) < 1) {
    const hours = Math.round((new Date(value).getTime() - Date.now()) / 3_600_000)
    return Math.abs(hours) < 1 ? 'az önce' : rtf.format(hours, 'hour')
  }
  if (Math.abs(days) < 30) return rtf.format(days, 'day')
  return formatDate(value)
}

export const initials = (name: string) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toLocaleUpperCase('tr-TR'))
    .join('')

// Mantine'in varsayılan araması toLowerCase kullanır: "İzmir" → "i̇zmir" olur ve "izm" eşleşmez. Türkçe küçültme ile ara.
export const trLower = (s: string) => s.toLocaleLowerCase('tr-TR')

export const trFilter: OptionsFilter = ({ options, search }) => {
  const q = trLower(search.trim())
  return (options as ComboboxItem[]).filter((o) => trLower(o.label).includes(q))
}
