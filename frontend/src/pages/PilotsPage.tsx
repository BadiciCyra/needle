import {
  Button,
  Group,
  Progress,
  ScrollArea,
  SegmentedControl,
  Table,
  Text,
} from '@mantine/core'
import { IconRocket } from '@tabler/icons-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth'
import { EmptyState, OrgAvatar, PageHeader, PageLoader, StatStrip, Tag } from '../components/ui'
import { useAppData } from '../data'
import { formatDate, PILOT_RESULT, PILOT_STATUS, TAG_COLOR, timeAgo } from '../labels'
import type { Pilot } from '../types'

const progressOf = (p: Pilot) => {
  const total = p.milestones.length
  const done = p.milestones.filter((m) => m.completed_at).length
  return { total, done, pct: total ? Math.round((done / total) * 100) : 0 }
}

export default function PilotsPage() {
  const { pilots } = useAppData()
  const { isAdmin, isStartup } = useAuth()
  const [filter, setFilter] = useState('active')
  const navigate = useNavigate()

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
                      Bitiş
                    </Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {shown.map((p) => {
                    const { total, done, pct } = progressOf(p)
                    const counterpart = isStartup ? p.organization ?? 'Kurum' : p.startup.name
                    return (
                      <Table.Tr key={p.id} className="app-row-link" onClick={() => navigate(`/pilotlar/${p.id}`)}>
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
                            {p.end_date ? formatDate(p.end_date) : formatDate(p.started_at)}
                            {p.overdue_milestones > 0 && p.status === 'active' && (
                              <Text span size="xs" c="var(--app-danger)" display="block">
                                {p.overdue_milestones} gecikme
                              </Text>
                            )}
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

    </>
  )
}
