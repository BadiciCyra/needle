import {
  ActionIcon,
  Anchor,
  Button,
  Checkbox,
  Divider,
  Drawer,
  Group,
  Progress,
  ScrollArea,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Textarea,
  TextInput,
  Title,
  Tooltip,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconPlus, IconRocket } from '@tabler/icons-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api'
import { useAuth } from '../auth'
import { EmptyState, MetaItem, OrgAvatar, PageHeader, PageLoader, StatStrip, Tag } from '../components/ui'
import { useAppData } from '../data'
import { formatDate, PILOT_RESULT, PILOT_STATUS, TAG_COLOR, timeAgo } from '../labels'
import type { Pilot, PilotResult, PilotStatus } from '../types'

const progressOf = (p: Pilot) => {
  const total = p.milestones.length
  const done = p.milestones.filter((m) => m.completed_at).length
  return { total, done, pct: total ? Math.round((done / total) * 100) : 0 }
}

function PilotDetail({ pilot, onChange }: { pilot: Pilot; onChange: (p: Pilot) => void }) {
  const { isStartup } = useAuth()
  const [title, setTitle] = useState('')
  const [due, setDue] = useState('')
  const [outcome, setOutcome] = useState(pilot.outcome ?? '')
  const { total, done, pct } = progressOf(pilot)

  const run = async (action: () => Promise<Pilot>, message?: string) => {
    try {
      onChange(await action())
      if (message) notifications.show({ color: 'teal', message })
    } catch (e) {
      notifications.show({ color: 'red', title: 'Kaydedilemedi', message: (e as Error).message })
    }
  }

  return (
    <Stack gap="lg">
      <Group gap="md" wrap="nowrap">
        <OrgAvatar name={isStartup ? pilot.organization ?? 'Kurum' : pilot.startup.name} size={48} />
        <div style={{ minWidth: 0 }}>
          <Title order={2} className="app-display" fw={400} fz={30}>
            {isStartup ? pilot.organization ?? 'Kurum' : pilot.startup.name}
          </Title>
          {isStartup ? (
            <Text size="sm" c="dimmed">
              {pilot.brief_title}
            </Text>
          ) : (
            <Anchor component={Link} to={`/ihtiyaclar/${pilot.brief_id}`} size="sm">
              {pilot.brief_title}
            </Anchor>
          )}
        </div>
      </Group>

      {pilot.stale && (
        <Tag color={TAG_COLOR.red}>
          <Text span size="sm" c={TAG_COLOR.red}>
            {pilot.days_inactive} gündür hareket yok
          </Text>
        </Tag>
      )}

      <SimpleGrid cols={2}>
        <Select
          label="Durum"
          disabled={isStartup}
          size="xs"
          styles={{ label: { fontSize: 12, fontWeight: 400, color: 'var(--app-muted)', marginBottom: 2 } }}
          value={pilot.status}
          allowDeselect={false}
          data={Object.entries(PILOT_STATUS).map(([value, s]) => ({ value, label: s.label }))}
          onChange={(value) => value && run(() => api.updatePilot(pilot.id, { status: value as PilotStatus }), 'Durum güncellendi')}
        />
        <MetaItem label="Başlangıç">{formatDate(pilot.started_at)}</MetaItem>
        <MetaItem label="Son hareket">{timeAgo(pilot.last_activity_at)}</MetaItem>
        <MetaItem label="İlerleme">
          {done}/{total} kilometre taşı
        </MetaItem>
      </SimpleGrid>

      <Divider />

      <div>
        <Group justify="space-between" mb="xs">
          <Text className="app-section-title">Kilometre taşları</Text>
          <Text size="sm" c="dimmed">
            %{pct}
          </Text>
        </Group>
        <Progress value={pct} color="thread.6" mb="md" />
        <Stack gap={10}>
          {pilot.milestones.length === 0 && (
            <Text size="sm" c="dimmed">
              Henüz kilometre taşı yok. Pilotun ilk adımlarını ekleyin; örneğin veri erişimi, kurulum, ilk ölçüm.
            </Text>
          )}
          {pilot.milestones.map((m) => (
            <Checkbox
              key={m.id}
              checked={!!m.completed_at}
              disabled={!!m.completed_at}
              onChange={() => run(() => api.completeMilestone(m.id), 'Kilometre taşı tamamlandı')}
              label={
                <Text size="sm" td={m.completed_at ? 'line-through' : undefined} c={m.completed_at ? 'dimmed' : undefined}>
                  {m.title}
                </Text>
              }
              description={
                m.completed_at ? `Tamamlandı · ${formatDate(m.completed_at)}` : m.due_date ? `Son tarih · ${formatDate(m.due_date)}` : undefined
              }
            />
          ))}
        </Stack>
        <Group gap="xs" mt="md" wrap="nowrap" align="flex-end">
          <TextInput
            placeholder="Yeni kilometre taşı"
            value={title}
            onChange={(e) => setTitle(e.currentTarget.value)}
            style={{ flex: 1 }}
          />
          <TextInput type="date" value={due} onChange={(e) => setDue(e.currentTarget.value)} w={150} />
          <Tooltip label="Ekle">
            <ActionIcon
              size={36}
              disabled={title.trim().length < 2}
              onClick={() =>
                run(async () => {
                  const p = await api.addMilestone(pilot.id, title.trim(), due)
                  setTitle('')
                  setDue('')
                  return p
                })
              }
              aria-label="Kilometre taşı ekle"
            >
              <IconPlus size={18} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </div>

      {!isStartup && (
        <>
      <Divider />

      <div>
        <Text className="app-section-title" mb={4}>
          İşe yaradı mı?
        </Text>
        <Text size="sm" c="dimmed" mb="sm">
          Deneme bitince tek dokunuşla işaretleyin. Bu bilgi, ileride benzer ihtiyaçlarda hangi girişimin öne çıkacağını
          belirlemek için kullanılacak.
        </Text>
        <Stack gap="sm">
          <SegmentedControl
            fullWidth
            value={pilot.result ?? ''}
            onChange={(value) => run(() => api.updatePilot(pilot.id, { result: value as PilotResult }), 'Sonuç kaydedildi')}
            data={[
              { value: 'evet', label: 'Evet' },
              { value: 'kismen', label: 'Kısmen' },
              { value: 'hayir', label: 'Hayır' },
            ]}
          />
          <Textarea
            placeholder="İsterseniz kısa bir not: ne işe yaradı, ne yaramadı?"
            autosize
            minRows={2}
            value={outcome}
            onChange={(e) => setOutcome(e.currentTarget.value)}
          />
          <Group justify="flex-end">
            <Button
              variant="default"
              disabled={outcome.trim() === (pilot.outcome ?? '')}
              onClick={() => run(() => api.updatePilot(pilot.id, { outcome: outcome.trim() }), 'Not kaydedildi')}
            >
              Notu kaydet
            </Button>
          </Group>
        </Stack>
      </div>
        </>
      )}
    </Stack>
  )
}

export default function PilotsPage() {
  const { pilots, setPilot } = useAppData()
  const { isAdmin, isStartup } = useAuth()
  const [filter, setFilter] = useState('active')
  const [openId, setOpenId] = useState<number | null>(null)
  const open = pilots?.find((p) => p.id === openId) ?? null

  const shown = useMemo(
    () => pilots?.filter((p) => (filter === 'all' ? true : filter === 'stale' ? p.stale : p.status === filter)) ?? [],
    [pilots, filter],
  )

  if (!pilots) return <PageLoader />

  const active = pilots.filter((p) => p.status === 'active')
  const stale = pilots.filter((p) => p.stale)
  const avg = active.length ? Math.round(active.reduce((s, p) => s + progressOf(p).pct, 0) / active.length) : 0

  return (
    <>
      <PageHeader
        title="Pilotlar"
        description="Tanıştırma kabul edilince açılır; kurum ve girişim aynı kartı görür. Uzun süre hareketsiz kalan pilotlar işaretlenir; pilotlar sessizce ölmesin."
      />

      <StatStrip
        items={[
          { label: 'Aktif', value: active.length, onClick: () => setFilter('active') },
          { label: 'Hareketsiz', value: stale.length, tone: stale.length ? 'alert' : undefined, onClick: () => setFilter('stale') },
          { label: 'Tamamlanan', value: pilots.filter((p) => p.status === 'done').length, onClick: () => setFilter('done') },
          { label: 'Ortalama ilerleme', value: `${avg}%`, hint: 'Aktif pilotlarda tamamlanan kilometre taşı' },
        ]}
      />

      {pilots.length === 0 ? (
        <EmptyState
          icon={IconRocket}
          title="Henüz pilot yok"
          description="Tanıştırma isteği kabul edildiğinde ya da bir çağrı başvurusunu kabul ettiğinizde pilot kartı açılır."
          action={
            <Button component={Link} to={isStartup ? '/tanistirmalar' : '/ihtiyaclar'} variant="default">
              {isStartup ? 'Tanıştırma isteklerine git' : 'İhtiyaçlara git'}
            </Button>
          }
        />
      ) : (
        <>
          <ScrollArea type="never" mb="md">
            <SegmentedControl
              value={filter}
              onChange={setFilter}
              data={[
                { value: 'active', label: 'Aktif' },
                { value: 'stale', label: 'Hareketsiz' },
                { value: 'paused', label: 'Duraklatılan' },
                { value: 'done', label: 'Tamamlanan' },
                { value: 'all', label: 'Tümü' },
              ]}
            />
          </ScrollArea>
          <div className="app-table-wrap">
            <Table.ScrollContainer minWidth={760}>
              <Table>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th pl="lg">{isStartup ? 'Kurum' : 'Girişim'}</Table.Th>
                    <Table.Th w={140}>Durum</Table.Th>
                    <Table.Th w={200}>İlerleme</Table.Th>
                    <Table.Th w={150} style={{ whiteSpace: 'nowrap' }}>
                      Son hareket
                    </Table.Th>
                    <Table.Th pr="lg" ta="right" w={130}>
                      Başlangıç
                    </Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {shown.map((p) => {
                    const { total, done, pct } = progressOf(p)
                    // Girişim kendi adını değil karşı tarafı (kurumu) görür
                    const counterpart = isStartup ? p.organization ?? 'Kurum' : p.startup.name
                    return (
                      <Table.Tr key={p.id} className="app-row-link" onClick={() => setOpenId(p.id)}>
                        <Table.Td pl="lg">
                          <Group gap="sm" wrap="nowrap">
                            <OrgAvatar name={counterpart} size={34} />
                            <div style={{ minWidth: 0 }}>
                              <Text size="sm" fw={600}>
                                {counterpart}
                              </Text>
                              <Text size="xs" c="dimmed" lineClamp={1}>
                                {isAdmin && p.organization ? `${p.organization} · ` : ''}
                                {p.brief_title}
                              </Text>
                            </div>
                          </Group>
                        </Table.Td>
                        <Table.Td>
                          <Tag color={PILOT_STATUS[p.status].color}>{PILOT_STATUS[p.status].label}</Tag>
                          {p.result && (
                            <Text size="xs" c="dimmed" mt={2}>
                              İşe yaradı mı: {PILOT_RESULT[p.result]}
                            </Text>
                          )}
                        </Table.Td>
                        <Table.Td>
                          <Group gap="xs" wrap="nowrap">
                            <Progress value={pct} color="ink" style={{ flex: 1 }} />
                            <Text size="xs" c="dimmed" w={34} ta="right" className="app-num">
                              {done}/{total}
                            </Text>
                          </Group>
                        </Table.Td>
                        <Table.Td>
                          {p.stale ? (
                            <Tag color={TAG_COLOR.red}>
                              <Text span size="sm" c={TAG_COLOR.red} className="app-num">
                                {p.days_inactive} gün
                              </Text>
                            </Tag>
                          ) : (
                            <Text size="sm" c="dimmed">
                              {timeAgo(p.last_activity_at)}
                            </Text>
                          )}
                        </Table.Td>
                        <Table.Td pr="lg" ta="right">
                          <Text size="sm" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
                            {formatDate(p.started_at)}
                          </Text>
                        </Table.Td>
                      </Table.Tr>
                    )
                  })}
                  {shown.length === 0 && (
                    <Table.Tr>
                      <Table.Td colSpan={5} py="xl" ta="center">
                        <Text size="sm" c="dimmed">
                          Bu filtrede pilot yok.
                        </Text>
                      </Table.Td>
                    </Table.Tr>
                  )}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          </div>
        </>
      )}

      <Drawer opened={open !== null} onClose={() => setOpenId(null)} title="Pilot detayı">
        {open && <PilotDetail key={open.id} pilot={open} onChange={setPilot} />}
      </Drawer>
    </>
  )
}
