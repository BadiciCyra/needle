import {
  ActionIcon,
  Alert,
  Anchor,
  Autocomplete,
  Button,
  Checkbox,
  Grid,
  Group,
  Menu,
  Modal,
  NumberInput,
  Progress,
  Rating,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconAlertCircle, IconDots, IconPencil, IconPlus, IconSparkles, IconTrash } from '@tabler/icons-react'
import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api'
import { useAuth } from '../auth'
import MetricChart from '../components/MetricChart'
import { MetaItem, OrgAvatar, PageLoader, SectionCard, Tag } from '../components/ui'
import { useAppData } from '../data'
import { formatDate, METRIC_UNITS, NEXT_STEP, OWNER_LABEL, PILOT_RESULT, PILOT_STATUS, ROLE_LABEL, suggestUnit, TAG_COLOR, timeAgo, withUnit } from '../labels'
import type { Metric, MetricInput, MilestoneOwner, NextStep, PilotDetail, PilotResult, PilotStatus } from '../types'

type Run = (action: () => Promise<PilotDetail>, message?: string) => Promise<boolean>

const fmt = (v: number | null, unit?: string | null) => (v === null ? '—' : withUnit(v, unit))
const dayInput = (value: string | null) => (value ? value.slice(0, 10) : '')

function PlanSection({ pilot, run }: { pilot: PilotDetail; run: Run }) {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ goal: '', scope: '', start_date: '', end_date: '', firm_contact: '', startup_contact: '' })
  const start = pilot.start_date ? new Date(pilot.start_date) : null
  const end = pilot.end_date ? new Date(pilot.end_date) : null
  const total = start && end ? Math.max(1, (end.getTime() - start.getTime()) / 86_400_000) : null
  const elapsed = start ? Math.max(0, (Date.now() - start.getTime()) / 86_400_000) : 0
  const left = end ? Math.ceil((end.getTime() - Date.now()) / 86_400_000) : null

  const edit = () => {
    setForm({
      goal: pilot.goal ?? '',
      scope: pilot.scope ?? '',
      start_date: dayInput(pilot.start_date),
      end_date: dayInput(pilot.end_date),
      firm_contact: pilot.firm_contact ?? '',
      startup_contact: pilot.startup_contact ?? '',
    })
    setOpen(true)
  }

  const save = async () => {
    const ok = await run(
      () =>
        api.updatePlan(pilot.id, {
          goal: form.goal || null,
          scope: form.scope || null,
          start_date: form.start_date || null,
          end_date: form.end_date || null,
          firm_contact: form.firm_contact || null,
          startup_contact: form.startup_contact || null,
        }),
      'Plan kaydedildi',
    )
    if (ok) setOpen(false)
  }

  const empty = !pilot.goal && !pilot.start_date
  return (
    <SectionCard
      title="Plan"
      description="Pilotun amacı, kapsamı, süresi ve iki tarafın sorumluları"
      action={
        <Group gap="xs">
          {(empty || pilot.milestones.length === 0) && (
            <Button size="xs" variant="default" leftSection={<IconSparkles size={14} />} onClick={() => run(() => api.fillPlanDefaults(pilot.id), 'Plan brief’ten dolduruldu')}>
              Brief’ten doldur
            </Button>
          )}
          <Button size="xs" variant="default" leftSection={<IconPencil size={14} />} onClick={edit}>
            Düzenle
          </Button>
        </Group>
      }
    >
      <Stack gap="md">
        <MetaItem label="Amaç">{pilot.goal ?? <Text span c="dimmed">Belirtilmedi</Text>}</MetaItem>
        {pilot.scope && <MetaItem label="Kapsam">{pilot.scope}</MetaItem>}
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <MetaItem label="Süre">
            {start ? formatDate(pilot.start_date) : '—'} → {end ? formatDate(pilot.end_date) : '—'}
            {left !== null && pilot.status === 'active' && (
              <Text span size="xs" c={left < 0 ? 'var(--app-danger)' : 'dimmed'}>
                {' '}
                · {left < 0 ? `${-left} gün gecikti` : `${left} gün kaldı`}
              </Text>
            )}
          </MetaItem>
          <MetaItem label="Sorumlular">
            <Text size="sm">Kurum: {pilot.firm_contact ?? '—'}</Text>
            <Text size="sm">Girişim: {pilot.startup_contact ?? '—'}</Text>
          </MetaItem>
        </SimpleGrid>
        {total && <Progress value={Math.min(100, (elapsed / total) * 100)} color={left !== null && left < 0 ? 'red' : 'ink'} />}
      </Stack>

      <Modal opened={open} onClose={() => setOpen(false)} size="lg" title={<Text fw={600}>Pilot planı</Text>}>
        <Stack>
          <Textarea label="Amaç" autosize minRows={2} value={form.goal} onChange={(e) => setForm({ ...form, goal: e.currentTarget.value })} />
          <Textarea label="Kapsam" autosize minRows={2} value={form.scope} onChange={(e) => setForm({ ...form, scope: e.currentTarget.value })} />
          <SimpleGrid cols={2}>
            <TextInput label="Başlangıç" type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.currentTarget.value })} />
            <TextInput label="Bitiş" type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.currentTarget.value })} />
            <TextInput label="Kurum sorumlusu" placeholder="Ad, e-posta" value={form.firm_contact} onChange={(e) => setForm({ ...form, firm_contact: e.currentTarget.value })} />
            <TextInput label="Girişim sorumlusu" placeholder="Ad, e-posta" value={form.startup_contact} onChange={(e) => setForm({ ...form, startup_contact: e.currentTarget.value })} />
          </SimpleGrid>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setOpen(false)}>
              Vazgeç
            </Button>
            <Button onClick={save}>Kaydet</Button>
          </Group>
        </Stack>
      </Modal>
    </SectionCard>
  )
}

const EMPTY_METRIC: MetricInput = { name: '', unit: '', baseline: null, target: null, direction: 'artis' }

function MetricForm({ initial, onSubmit, onCancel }: { initial: MetricInput; onSubmit: (m: MetricInput) => void; onCancel: () => void }) {
  const [m, setM] = useState<MetricInput>(initial)
  const [unitTouched, setUnitTouched] = useState(!!initial.unit)
  const num = (v: string | number) => (v === '' ? null : Number(v))
  const unit = m.unit?.trim() || null
  const percent = unit === '%'
  const unitSuffix = unit ? (
    <Text size="xs" c="dimmed" pr={28} style={{ whiteSpace: 'nowrap' }}>
      {unit}
    </Text>
  ) : undefined
  const valueProps = {
    decimalSeparator: ',',
    min: percent ? 0 : undefined,
    max: percent ? 100 : undefined,
    rightSection: unitSuffix,
    rightSectionWidth: unit ? 64 : undefined,
  }
  const setName = (name: string) => setM({ ...m, name, unit: unitTouched ? m.unit : (suggestUnit(name) ?? '') })
  return (
    <Stack>
      <TextInput label="Hedef" placeholder="Örn. Şikayetlerin doğru kategoriye atanma oranı" value={m.name} onChange={(e) => setName(e.currentTarget.value)} />
      <SimpleGrid cols={{ base: 1, xs: 3 }}>
        <Autocomplete
          label="Birim"
          description={!unitTouched && unit ? 'Addan önerildi' : 'Seçin ya da yazın'}
          placeholder="Seçin ya da yazın"
          data={METRIC_UNITS}
          value={m.unit ?? ''}
          onChange={(v) => {
            setUnitTouched(true)
            setM({ ...m, unit: v })
          }}
          maxLength={20}
          comboboxProps={{ withinPortal: true }}
        />
        <NumberInput label="Başlangıç değeri" description="Pilottan önce" {...valueProps} value={m.baseline ?? ''} onChange={(v) => setM({ ...m, baseline: num(v) })} />
        <NumberInput label="Hedef değer" description="Pilot sonunda" {...valueProps} value={m.target ?? ''} onChange={(v) => setM({ ...m, target: num(v) })} />
      </SimpleGrid>
      <div>
        <Text size="sm" fw={500} mb={4}>
          Yön
        </Text>
        <SegmentedControl
          value={m.direction}
          onChange={(v) => setM({ ...m, direction: v as MetricInput['direction'] })}
          data={[
            { value: 'artis', label: 'Artması iyi' },
            { value: 'azalis', label: 'Azalması iyi' },
          ]}
        />
      </div>
      <Group justify="flex-end">
        <Button variant="default" onClick={onCancel}>
          Vazgeç
        </Button>
        <Button disabled={m.name.trim().length < 2} onClick={() => onSubmit({ ...m, name: m.name.trim(), unit: m.unit?.trim() || null })}>
          Kaydet
        </Button>
      </Group>
    </Stack>
  )
}

function MetricRow({ metric, run }: { metric: Metric; run: Run }) {
  const [value, setValue] = useState<string | number>('')
  const [date, setDate] = useState('')
  const [editing, setEditing] = useState(false)
  const color = metric.achieved ? 'green' : 'ink'
  return (
    <Stack gap="xs" className="app-list-row" p="md">
      <Group justify="space-between" wrap="nowrap" align="flex-start">
        <div style={{ minWidth: 0 }}>
          <Text fw={600} size="sm">
            {metric.name}
          </Text>
          <Text size="xs" c="dimmed">
            Şu an {fmt(metric.latest, metric.unit)} · hedef {fmt(metric.target, metric.unit)}
            {metric.baseline !== null ? ` · başlangıç ${fmt(metric.baseline, metric.unit)}` : ''} ·{' '}
            {metric.direction === 'artis' ? 'artması iyi' : 'azalması iyi'}
          </Text>
        </div>
        <Group gap={6} wrap="nowrap">
          {metric.achieved && <Tag color={TAG_COLOR.green}>Hedef tuttu</Tag>}
          <Menu position="bottom-end">
            <Menu.Target>
              <ActionIcon variant="subtle" color="gray" aria-label="Hedef işlemleri">
                <IconDots size={16} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item leftSection={<IconPencil size={14} />} onClick={() => setEditing(true)}>
                Düzenle
              </Menu.Item>
              <Menu.Item color="red" leftSection={<IconTrash size={14} />} onClick={() => run(() => api.deleteMetric(metric.id), 'Hedef silindi')}>
                Sil
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>
      </Group>
      {metric.progress !== null && <Progress value={metric.progress * 100} color={color} />}
      <MetricChart metric={metric} />
      <Group gap="xs" wrap="nowrap" align="flex-end">
        <NumberInput size="xs" placeholder="Yeni ölçüm" decimalSeparator="," value={value} onChange={setValue} style={{ flex: 1 }} />
        <TextInput size="xs" type="date" value={date} onChange={(e) => setDate(e.currentTarget.value)} w={140} />
        <Button
          size="xs"
          disabled={value === ''}
          onClick={async () => {
            if (await run(() => api.addMeasurement(metric.id, Number(value), date), 'Ölçüm eklendi')) {
              setValue('')
              setDate('')
            }
          }}
        >
          Ekle
        </Button>
      </Group>
      <Modal opened={editing} onClose={() => setEditing(false)} title={<Text fw={600}>Hedefi düzenle</Text>}>
        <MetricForm
          initial={{ name: metric.name, unit: metric.unit, baseline: metric.baseline, target: metric.target, direction: metric.direction }}
          onCancel={() => setEditing(false)}
          onSubmit={async (m) => (await run(() => api.editMetric(metric.id, m), 'Hedef güncellendi')) && setEditing(false)}
        />
      </Modal>
    </Stack>
  )
}

function MetricsSection({ pilot, run }: { pilot: PilotDetail; run: Run }) {
  const [adding, setAdding] = useState(false)
  return (
    <SectionCard
      title="Ölçülebilir hedefler"
      description="Başarı kriterini sayıya bağlayın; ölçümler eklendikçe gidişat çizilir"
      padding="0"
      action={
        <Button size="xs" variant="default" leftSection={<IconPlus size={14} />} onClick={() => setAdding(true)}>
          Hedef ekle
        </Button>
      }
    >
      {pilot.metrics.length === 0 ? (
        <Text size="sm" c="dimmed" p="lg">
          Henüz hedef yok. Örneğin “Şikayetlerin %85’i doğru kategoriye atansın” gibi ölçülebilir bir hedef ekleyin.
        </Text>
      ) : (
        pilot.metrics.map((m) => <MetricRow key={m.id} metric={m} run={run} />)
      )}
      <Modal opened={adding} onClose={() => setAdding(false)} title={<Text fw={600}>Ölçülebilir hedef ekle</Text>}>
        <MetricForm
          initial={EMPTY_METRIC}
          onCancel={() => setAdding(false)}
          onSubmit={async (m) => (await run(() => api.addMetric(pilot.id, m), 'Hedef eklendi')) && setAdding(false)}
        />
      </Modal>
    </SectionCard>
  )
}

function MilestonesSection({ pilot, run }: { pilot: PilotDetail; run: Run }) {
  const [title, setTitle] = useState('')
  const [due, setDue] = useState('')
  const [owner, setOwner] = useState<MilestoneOwner>('ortak')
  const done = pilot.milestones.filter((m) => m.completed_at).length
  return (
    <SectionCard
      title="Kilometre taşları"
      description={`${done}/${pilot.milestones.length} tamamlandı${pilot.overdue_milestones ? ` · ${pilot.overdue_milestones} gecikmede` : ''}`}
      padding="0"
    >
      {pilot.milestones.map((m) => (
        <Group key={m.id} className="app-list-row" px="lg" py="sm" justify="space-between" wrap="nowrap">
          <Checkbox
            checked={!!m.completed_at}
            onChange={() => run(() => (m.completed_at ? api.reopenMilestone(m.id) : api.completeMilestone(m.id)))}
            label={
              <Text size="sm" td={m.completed_at ? 'line-through' : undefined} c={m.completed_at ? 'dimmed' : undefined}>
                {m.title}
              </Text>
            }
            description={
              m.completed_at ? (
                `Tamamlandı · ${formatDate(m.completed_at)}`
              ) : m.due_date ? (
                <Text span size="xs" c={m.overdue ? 'var(--app-danger)' : 'dimmed'}>
                  {m.overdue ? 'Gecikti · ' : 'Son tarih · '}
                  {formatDate(m.due_date)}
                </Text>
              ) : undefined
            }
          />
          <Group gap={6} wrap="nowrap">
            <Tag color={m.owner === 'kurum' ? TAG_COLOR.slate : m.owner === 'girisim' ? TAG_COLOR.thread : TAG_COLOR.gray}>{OWNER_LABEL[m.owner]}</Tag>
            <Tooltip label="Sil">
              <ActionIcon variant="subtle" color="gray" aria-label="Kilometre taşını sil" onClick={() => run(() => api.deleteMilestone(m.id))}>
                <IconTrash size={14} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>
      ))}
      <Group gap="xs" p="md" wrap="nowrap" align="flex-end" style={{ borderTop: '1px solid var(--app-border)' }}>
        <TextInput size="xs" placeholder="Yeni kilometre taşı" value={title} onChange={(e) => setTitle(e.currentTarget.value)} style={{ flex: 1 }} />
        <TextInput size="xs" type="date" value={due} onChange={(e) => setDue(e.currentTarget.value)} w={140} />
        <Select
          size="xs"
          w={110}
          allowDeselect={false}
          value={owner}
          onChange={(v) => v && setOwner(v as MilestoneOwner)}
          data={(['ortak', 'kurum', 'girisim'] as MilestoneOwner[]).map((o) => ({ value: o, label: OWNER_LABEL[o] }))}
        />
        <Button
          size="xs"
          disabled={title.trim().length < 2}
          onClick={async () => {
            if (await run(() => api.addMilestone(pilot.id, title.trim(), due, owner))) {
              setTitle('')
              setDue('')
            }
          }}
        >
          Ekle
        </Button>
      </Group>
    </SectionCard>
  )
}

function EvaluationSection({ pilot, run }: { pilot: PilotDetail; run: Run }) {
  const { isStartup } = useAuth()
  const [editing, setEditing] = useState(!pilot.evaluated_at)
  const [result, setResult] = useState<PilotResult>(pilot.result ?? 'evet')
  const [nextStep, setNextStep] = useState<NextStep | null>(pilot.next_step)
  const [rating, setRating] = useState(pilot.startup_rating ?? 0)
  const [comment, setComment] = useState(pilot.outcome ?? '')
  const [feedback, setFeedback] = useState(pilot.startup_feedback ?? '')
  const [collab, setCollab] = useState(pilot.collab_rating ?? 0)

  const firmSummary = pilot.evaluated_at && (
    <Stack gap={6}>
      <Group gap="xs">
        <Tag color={pilot.result === 'evet' ? TAG_COLOR.green : pilot.result === 'kismen' ? TAG_COLOR.ochre : TAG_COLOR.gray}>
          İşe yaradı mı: {pilot.result ? PILOT_RESULT[pilot.result] : '—'}
        </Tag>
        {pilot.next_step && <Tag color={TAG_COLOR.slate}>{NEXT_STEP[pilot.next_step]}</Tag>}
      </Group>
      {pilot.startup_rating && <Rating value={pilot.startup_rating} readOnly size="sm" />}
      {pilot.outcome && <Text size="sm">{pilot.outcome}</Text>}
      <Text size="xs" c="dimmed">
        Kurum {formatDate(pilot.evaluated_at)} tarihinde değerlendirdi
      </Text>
    </Stack>
  )

  const startupSummary = pilot.startup_feedback && (
    <div className="app-evidence">
      <Text size="xs" c="dimmed">
        Girişimin değerlendirmesi{pilot.collab_rating ? ` · iş birliği ${pilot.collab_rating}/5` : ''}
      </Text>
      <Text size="sm">{pilot.startup_feedback}</Text>
    </div>
  )

  if (isStartup)
    return (
      <SectionCard title="Değerlendirme" description="Pilotun sonucu kurumca, iş birliği deneyimi sizce değerlendirilir">
        <Stack gap="md">
          {firmSummary || (
            <Text size="sm" c="dimmed">
              Kurum pilotu henüz kapatmadı.
            </Text>
          )}
          <Textarea
            label="Sizin değerlendirmeniz"
            description="Kurumla çalışmak nasıldı, neyi farklı yapardınız? Kurum ve program yöneticisi görür."
            autosize
            minRows={3}
            value={feedback}
            onChange={(e) => setFeedback(e.currentTarget.value)}
          />
          <Group justify="space-between">
            <Group gap="xs">
              <Text size="sm">İş birliği</Text>
              <Rating value={collab} onChange={setCollab} />
            </Group>
            <Button
              size="xs"
              disabled={feedback.trim().length < 10}
              onClick={() => run(() => api.startupFeedback(pilot.id, { feedback: feedback.trim(), collab_rating: collab || null }), 'Değerlendirmeniz kaydedildi')}
            >
              Kaydet
            </Button>
          </Group>
        </Stack>
      </SectionCard>
    )

  return (
    <SectionCard
      title="Kapanış değerlendirmesi"
      description="Pilot bitince işe yarayıp yaramadığını ve sonraki adımı kaydedin; pilot tamamlandı olarak kapanır"
      action={
        pilot.evaluated_at && !editing ? (
          <Button size="xs" variant="default" onClick={() => setEditing(true)}>
            Güncelle
          </Button>
        ) : undefined
      }
    >
      <Stack gap="md">
        {pilot.evaluated_at && !editing ? (
          firmSummary
        ) : (
          <>
            <div>
              <Text size="sm" fw={500} mb={4}>
                İşe yaradı mı?
              </Text>
              <SegmentedControl
                fullWidth
                value={result}
                onChange={(v) => setResult(v as PilotResult)}
                data={[
                  { value: 'evet', label: 'Evet' },
                  { value: 'kismen', label: 'Kısmen' },
                  { value: 'hayir', label: 'Hayır' },
                ]}
              />
            </div>
            <Select
              label="Sonraki adım"
              placeholder="Seçin"
              value={nextStep}
              onChange={(v) => setNextStep(v as NextStep | null)}
              data={(Object.keys(NEXT_STEP) as NextStep[]).map((k) => ({ value: k, label: NEXT_STEP[k] }))}
            />
            <Group gap="xs">
              <Text size="sm" fw={500}>
                Girişime puan
              </Text>
              <Rating value={rating} onChange={setRating} />
            </Group>
            <Textarea label="Not" placeholder="Ne işe yaradı, ne yaramadı?" autosize minRows={2} value={comment} onChange={(e) => setComment(e.currentTarget.value)} />
            <Group justify="flex-end">
              {pilot.evaluated_at && (
                <Button variant="default" size="xs" onClick={() => setEditing(false)}>
                  Vazgeç
                </Button>
              )}
              <Button
                size="xs"
                disabled={!nextStep || !rating}
                onClick={async () => {
                  const ok = await run(
                    () => api.evaluatePilot(pilot.id, { result, next_step: nextStep!, startup_rating: rating, comment: comment.trim() || undefined }),
                    'Pilot değerlendirildi ve kapatıldı',
                  )
                  if (ok) setEditing(false)
                }}
              >
                {pilot.evaluated_at ? 'Kaydet' : 'Değerlendir ve kapat'}
              </Button>
            </Group>
          </>
        )}
        {startupSummary}
      </Stack>
    </SectionCard>
  )
}

function ActivitySection({ pilot, run }: { pilot: PilotDetail; run: Run }) {
  const [body, setBody] = useState('')
  return (
    <SectionCard title="Güncellemeler" description="İki tarafın notları ve pilottaki her değişiklik" padding="0">
      <Stack gap="xs" p="md" style={{ borderBottom: '1px solid var(--app-border)' }}>
        <Textarea placeholder="Karşı tarafa bir not yazın: ilerleme, ihtiyaç, soru…" autosize minRows={2} value={body} onChange={(e) => setBody(e.currentTarget.value)} />
        <Group justify="flex-end">
          <Button
            size="xs"
            disabled={body.trim().length < 2}
            onClick={async () => {
              if (await run(() => api.addNote(pilot.id, body.trim()))) setBody('')
            }}
          >
            Gönder
          </Button>
        </Group>
      </Stack>
      <Stack gap={0} mah={560} style={{ overflowY: 'auto' }}>
        {pilot.activity.map((a) =>
          a.kind === 'not' ? (
            <div key={a.id} className="app-list-row" style={{ padding: '12px 16px' }}>
              <Group gap={6} mb={4}>
                <Tag color={a.author_role === 'girisim' ? TAG_COLOR.thread : TAG_COLOR.slate}>{ROLE_LABEL[a.author_role] ?? a.author_role}</Tag>
                <Text size="xs" c="dimmed">
                  {a.author_name} · {timeAgo(a.created_at)}
                </Text>
              </Group>
              <Text size="sm" style={{ whiteSpace: 'pre-line' }}>
                {a.body}
              </Text>
            </div>
          ) : (
            <Group key={a.id} className="app-list-row" gap={8} px="md" py={8} wrap="nowrap" align="flex-start">
              <Text size="xs" c="dimmed" style={{ flex: 1 }}>
                {a.body}
                {a.author_name ? ` · ${a.author_name}` : ''}
              </Text>
              <Text size="xs" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
                {timeAgo(a.created_at)}
              </Text>
            </Group>
          ),
        )}
      </Stack>
    </SectionCard>
  )
}

export default function PilotDetailPage() {
  const pilotId = Number(useParams().pilotId)
  const { isStartup } = useAuth()
  const { setPilot: setListPilot } = useAppData()
  const [pilot, setPilot] = useState<PilotDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.pilot(pilotId).then(setPilot).catch((e) => setError((e as Error).message))
  }, [pilotId])

  const run: Run = useCallback(
    async (action, message) => {
      try {
        const updated = await action()
        setPilot(updated)
        setListPilot(updated)
        if (message) notifications.show({ color: 'teal', message })
        return true
      } catch (e) {
        notifications.show({ color: 'red', title: 'Kaydedilemedi', message: (e as Error).message })
        return false
      }
    },
    [setListPilot],
  )

  if (error)
    return (
      <Alert color="red" variant="light" icon={<IconAlertCircle size={18} />} title="Pilot yüklenemedi">
        {error}{' '}
        <Anchor component={Link} to="/pilotlar">
          Pilotlara dön
        </Anchor>
      </Alert>
    )
  if (!pilot) return <PageLoader />

  const counterpart = isStartup ? pilot.organization ?? 'Kurum' : pilot.startup.name
  const status = PILOT_STATUS[pilot.status]
  const warnings: ReactNode[] = []
  if (pilot.stale) warnings.push(`${pilot.days_inactive} gündür hareket yok. Bir not yazın ya da bir kilometre taşını güncelleyin.`)
  if (pilot.overdue_milestones) warnings.push(`${pilot.overdue_milestones} kilometre taşının tarihi geçti.`)

  return (
    <>
      <Group gap={6} mb={10}>
        <Anchor component={Link} to="/pilotlar" size="sm" c="dimmed">
          Pilotlar
        </Anchor>
        <Text size="sm" c="dimmed">
          / #{pilot.id}
        </Text>
      </Group>
      <Group justify="space-between" align="flex-end" mb="lg" wrap="wrap" gap="md">
        <Group gap="md" wrap="nowrap" style={{ minWidth: 0 }}>
          <OrgAvatar name={counterpart} size={48} />
          <div style={{ minWidth: 0 }}>
            <Title order={1} className="app-display">
              {counterpart}
            </Title>
            <Group gap="xs" mt={6}>
              <Tag color={status.color}>{status.label}</Tag>
              {isStartup ? (
                <Text size="sm" c="dimmed">
                  {pilot.brief_title}
                </Text>
              ) : (
                <Anchor component={Link} to={`/ihtiyaclar/${pilot.brief_id}`} size="sm">
                  {pilot.brief_title}
                </Anchor>
              )}
              <Text size="sm" c="dimmed">
                · son hareket {timeAgo(pilot.last_activity_at)}
              </Text>
            </Group>
          </div>
        </Group>
        {!isStartup && (
          <Select
            w={180}
            allowDeselect={false}
            value={pilot.status}
            data={(Object.keys(PILOT_STATUS) as PilotStatus[]).map((s) => ({ value: s, label: PILOT_STATUS[s].label }))}
            onChange={(v) => v && v !== pilot.status && run(() => api.updatePilot(pilot.id, { status: v as PilotStatus }), 'Durum güncellendi')}
          />
        )}
      </Group>

      {warnings.length > 0 && pilot.status === 'active' && (
        <Alert color="red" variant="light" icon={<IconAlertCircle size={18} />} mb="lg">
          {warnings.map((w, i) => (
            <Text key={i} size="sm">
              {w}
            </Text>
          ))}
        </Alert>
      )}

      <Grid gap="lg">
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Stack gap="lg">
            <PlanSection pilot={pilot} run={run} />
            <MetricsSection pilot={pilot} run={run} />
            <MilestonesSection pilot={pilot} run={run} />
          </Stack>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 5 }}>
          <Stack gap="lg">
            <EvaluationSection key={pilot.evaluated_at ?? 'yok'} pilot={pilot} run={run} />
            <ActivitySection pilot={pilot} run={run} />
          </Stack>
        </Grid.Col>
      </Grid>
    </>
  )
}
