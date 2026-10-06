import {
  Accordion,
  Alert,
  Anchor,
  Button,
  Card,
  Group,
  Modal,
  Progress,
  Stack,
  Table,
  Text,
  Textarea,
  Timeline,
  Tooltip,
  UnstyledButton,
} from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconCheck, IconInfoCircle, IconMapPin, IconRoute, IconX } from '@tabler/icons-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api'
import { useAppData } from '../data'
import { MATURITY_LABEL, TAG_COLOR } from '../labels'
import type { MatchItem, MatchView, StartupProfile } from '../types'
import StartupDrawer from './StartupDrawer'
import { OrgAvatar, Tag } from './ui'

function StatusBadge({ item }: { item: MatchItem }) {
  if (item.status === 'accepted')
    return (
      <Tag color={TAG_COLOR.green}>Pilot açıldı</Tag>
    )
  if (item.status === 'declined')
    return (
      <Tag color={TAG_COLOR.gray} tooltip={item.declined_reason ?? 'Sebep yazılmadı'}>
        Reddedildi
      </Tag>
    )
  return null
}

function CandidateCard({
  item,
  topScore,
  onOpen,
  onDecide,
}: {
  item: MatchItem
  topScore: number
  onOpen: (s: StartupProfile) => void
  onDecide: (item: MatchItem, d: 'accept' | 'decline') => void
}) {
  const r = item.rationale
  const relative = topScore > 0 ? Math.round((item.score / topScore) * 100) : 0
  const s = item.startup
  return (
    <Card style={item.status === 'declined' ? { opacity: 0.6 } : undefined}>
      <Stack gap="md">
        <Group justify="space-between" align="flex-start" wrap="nowrap" gap="md">
          <Group gap="sm" wrap="nowrap" align="flex-start" style={{ minWidth: 0 }}>
            <OrgAvatar name={s.name} size={42} />
            <div style={{ minWidth: 0 }}>
              <Group gap={8}>
                <UnstyledButton onClick={() => onOpen(s)}>
                  <Text className="app-display" fz={24} lh={1.1} style={{ textDecoration: 'underline', textDecorationColor: 'var(--app-border-strong)', textDecorationThickness: 1, textUnderlineOffset: 5 }}>
                    {s.name}
                  </Text>
                </UnstyledButton>
                <StatusBadge item={item} />
              </Group>
              <Group gap={6} mt={4}>
                <Text size="xs" c="dimmed">
                  {s.sector}
                </Text>
                <Text size="xs" c="dimmed">
                  ·
                </Text>
                <Text size="xs" c="dimmed">
                  {MATURITY_LABEL[s.maturity]}
                </Text>
                <Text size="xs" c="dimmed">
                  ·
                </Text>
                <Group gap={2}>
                  <IconMapPin size={12} color="var(--app-muted)" />
                  <Text size="xs" c="dimmed">
                    {s.location}
                  </Text>
                </Group>
              </Group>
            </div>
          </Group>
          <Tooltip
            label={`Skor ${item.score.toFixed(3)} · vektör benzerliği ${item.vector_score.toFixed(3)}. Çubuk, listedeki en iyi adaya göre görelidir.`}
            multiline
            w={260}
          >
            <Stack gap={4} align="flex-end" miw={120}>
              <Text className="app-label">
                #{String(item.rank).padStart(2, '0')} · göreli uyum
              </Text>
              <Group gap={8} wrap="nowrap">
                <Progress value={relative} w={72} />
                <Text size="sm" className="app-num">
                  {relative}%
                </Text>
              </Group>
            </Stack>
          </Tooltip>
        </Group>

        {r ? (
          <Stack gap="sm">
            <Text size="sm" fw={500} lh={1.55}>
              {r.fit_summary}
            </Text>
            {r.evidence.map((e, i) => (
              <div key={i} className="app-evidence">
                <Text size="sm">
                  <Text span c="dimmed">
                    İhtiyaçtaki
                  </Text>{' '}
                  <Text span fw={600}>
                    “{e.brief_phrase}”
                  </Text>{' '}
                  <Text span c="dimmed">
                    ↔ girişimin
                  </Text>{' '}
                  <Text span fw={600} c="var(--app-accent-text)">
                    {e.startup_capability}
                  </Text>
                </Text>
                <Text size="xs" c="dimmed" mt={2}>
                  {e.explanation}
                </Text>
              </div>
            ))}
          </Stack>
        ) : (
          <Text size="sm" c="dimmed" lineClamp={2}>
            {s.description}
          </Text>
        )}

        {item.filter_notes.length > 0 && (
          <Alert variant="light" color="yellow" p="xs" icon={<IconInfoCircle size={16} />}>
            <Text size="xs">Kurumun tercihi dışında: {item.filter_notes.join('; ')}</Text>
          </Alert>
        )}

        {item.status === 'suggested' && (
          <Group justify="flex-end" gap="xs">
            <Button variant="default" size="xs" leftSection={<IconX size={14} />} onClick={() => onDecide(item, 'decline')}>
              Reddet
            </Button>
            <Button size="xs" leftSection={<IconCheck size={14} />} onClick={() => onDecide(item, 'accept')}>
              Kabul et ve pilot aç
            </Button>
          </Group>
        )}
      </Stack>
    </Card>
  )
}

export default function MatchResults({ view, onChange }: { view: MatchView; onChange: (v: MatchView) => void }) {
  const { refresh } = useAppData()
  const [declining, setDeclining] = useState<MatchItem | null>(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [drawer, setDrawer] = useState<StartupProfile | null>(null)
  const topScore = Math.max(0, ...view.shortlist.map((i) => i.score), ...view.rejected.map((i) => i.score))

  const decide = async (item: MatchItem, decision: 'accept' | 'decline', why?: string) => {
    setBusy(true)
    try {
      await api.decide(item.match_id, decision, why)
      onChange({
        ...view,
        shortlist: view.shortlist.map((i) =>
          i.match_id === item.match_id ? { ...i, status: decision === 'accept' ? 'accepted' : 'declined', declined_reason: why } : i,
        ),
      })
      refresh()
      notifications.show(
        decision === 'accept'
          ? {
              color: 'teal',
              title: 'Pilot açıldı',
              message: (
                <>
                  {item.startup.name} için pilot kartı oluşturuldu.{' '}
                  <Anchor component={Link} to="/pilotlar" size="sm">
                    Pilotlara git
                  </Anchor>
                </>
              ),
            }
          : { title: 'Aday reddedildi', message: `${item.startup.name} için ret kaydı tutuldu.` },
      )
    } catch (e) {
      notifications.show({ color: 'red', title: 'Karar kaydedilemedi', message: (e as Error).message })
    } finally {
      setBusy(false)
      setDeclining(null)
      setReason('')
    }
  }

  return (
    <Stack gap="md">
      {view.shortlist.length === 0 && (
        <Alert variant="light" color="gray" icon={<IconInfoCircle size={18} />}>
          Bu ihtiyaç için yeterince güçlü bir eşleşme bulunamadı. En yakın adaylar aşağıda gerekçeleriyle listeleniyor.
        </Alert>
      )}
      {view.shortlist.map((item) => (
        <CandidateCard
          key={item.match_id}
          item={item}
          topScore={topScore}
          onOpen={setDrawer}
          onDecide={(i, d) => (d === 'accept' ? decide(i, d) : setDeclining(i))}
        />
      ))}

      {view.rejected.length > 0 && (
        <Card padding={0}>
          <Group px="lg" pt="md" pb="xs" justify="space-between">
            <div>
              <div className="app-section-title">Yakındı ama…</div>
              <Text size="sm" c="dimmed">
                Elenen adaylar da gerekçesiyle saklanır.
              </Text>
            </div>
          </Group>
          <Table>
            <Table.Tbody>
              {view.rejected.map((item) => (
                <Table.Tr key={item.match_id} className="app-row-link" onClick={() => setDrawer(item.startup)}>
                  <Table.Td pl="lg" w={220}>
                    <Group gap="sm" wrap="nowrap">
                      <OrgAvatar name={item.startup.name} size={28} color="gray" />
                      <Text size="sm" fw={600}>
                        {item.startup.name}
                      </Text>
                    </Group>
                  </Table.Td>
                  <Table.Td pr="lg">
                    <Text size="sm">{item.rejection?.near_miss_reason}</Text>
                    {item.rejection?.missing_capability && (
                      <Text size="xs" c="dimmed">
                        Eksik yetkinlik: {item.rejection.missing_capability}
                      </Text>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Card>
      )}

      <Accordion variant="contained" radius="lg">
        <Accordion.Item value="trace">
          <Accordion.Control icon={<IconRoute size={18} />}>
            <Text size="sm" fw={500}>
              Arama izi
            </Text>
            <Text size="xs" c="dimmed">
              Adaylar nasıl bulundu: sorgular, filtre gevşetme, yeniden sıralama
            </Text>
          </Accordion.Control>
          <Accordion.Panel>
            <Timeline bulletSize={10} lineWidth={1} active={view.retrieval_trace.length}>
              {view.retrieval_trace.map((line, i) => (
                <Timeline.Item key={i}>
                  <Text size="sm">{line}</Text>
                </Timeline.Item>
              ))}
            </Timeline>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>

      <StartupDrawer startup={drawer} onClose={() => setDrawer(null)} />

      <Modal opened={declining !== null} onClose={() => setDeclining(null)} title={<Text fw={600}>{declining?.startup.name} adayını reddet</Text>}>
        <Stack>
          <Textarea
            label="Ret sebebi"
            description="Negatif eşleşme olarak saklanır; aynı hatanın tekrarlanmaması için kullanılır."
            placeholder="Örn. Bütçe uymadı, mevcut sistemlerle entegrasyonu zor…"
            autosize
            minRows={3}
            value={reason}
            onChange={(e) => setReason(e.currentTarget.value)}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeclining(null)}>
              Vazgeç
            </Button>
            <Button color="red" loading={busy} onClick={() => declining && decide(declining, 'decline', reason.trim() || undefined)}>
              Reddet
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  )
}
