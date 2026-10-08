import { Alert, Anchor, Button, Card, Grid, Group, Modal, Stack, Text, Textarea, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconAlertCircle, IconCheck, IconX } from '@tabler/icons-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api'
import { useAuth } from '../auth'
import StartupDrawer from '../components/StartupDrawer'
import { EmptyState, MetaItem, OrgAvatar, PageLoader, SectionCard, Tag } from '../components/ui'
import { useAppData } from '../data'
import { formatDate, MATURITY_LABEL, TAG_COLOR, timeAgo } from '../labels'
import type { Application, OpenCall, StartupProfile } from '../types'
import { callTag } from './CallsPage'

const APP_STATUS = {
  yeni: { label: 'Değerlendirme bekliyor', color: TAG_COLOR.ochre },
  kabul: { label: 'Kabul edildi · pilot açıldı', color: TAG_COLOR.green },
  ret: { label: 'Olumsuz', color: TAG_COLOR.gray },
}

function ApplicationCard({
  app,
  onOpen,
  onDecide,
}: {
  app: Application
  onOpen: (s: StartupProfile) => void
  onDecide?: (a: Application, d: 'kabul' | 'ret') => void
}) {
  const s = app.startup
  const status = APP_STATUS[app.status]
  return (
    <Card>
      <Stack gap="sm">
        <Group justify="space-between" wrap="nowrap" align="flex-start">
          <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
            <OrgAvatar name={s.name} size={38} />
            <div style={{ minWidth: 0 }}>
              <Anchor component="button" onClick={() => onOpen(s)} c="var(--app-ink)" fw={600}>
                {s.name}
              </Anchor>
              <Text size="xs" c="dimmed">
                {s.sector} · {s.location} · {MATURITY_LABEL[s.maturity]} · {timeAgo(app.created_at)}
              </Text>
            </div>
          </Group>
          <Tag color={status.color}>{status.label}</Tag>
        </Group>
        <Text size="sm" style={{ whiteSpace: 'pre-line' }}>
          {app.note}
        </Text>
        {app.decision_note && (
          <Text size="xs" c="dimmed">
            Notunuz: {app.decision_note}
          </Text>
        )}
        <Group justify="flex-end" gap="xs">
          {app.pilot_id && (
            <Button component={Link} to="/pilotlar" size="xs" variant="default">
              Pilota git
            </Button>
          )}
          {app.status === 'yeni' && onDecide && (
            <>
              <Button variant="default" size="xs" leftSection={<IconX size={14} />} onClick={() => onDecide(app, 'ret')}>
                Olumsuz
              </Button>
              <Button size="xs" leftSection={<IconCheck size={14} />} onClick={() => onDecide(app, 'kabul')}>
                Kabul et ve pilot aç
              </Button>
            </>
          )}
        </Group>
      </Stack>
    </Card>
  )
}

export default function CallDetailPage() {
  const callId = Number(useParams().callId)
  const { isStartup, me } = useAuth()
  const { refresh } = useAppData()
  const [call, setCall] = useState<OpenCall | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [deciding, setDeciding] = useState<{ app: Application; decision: 'kabul' | 'ret' } | null>(null)
  const [decisionNote, setDecisionNote] = useState('')
  const [drawer, setDrawer] = useState<StartupProfile | null>(null)

  const load = useCallback(() => {
    api.call(callId).then(setCall).catch((e) => setError((e as Error).message))
  }, [callId])
  useEffect(load, [load])

  const run = async (action: () => Promise<OpenCall>, message: string) => {
    setBusy(true)
    try {
      setCall(await action())
      refresh()
      notifications.show({ color: 'teal', message })
      return true
    } catch (e) {
      notifications.show({ color: 'red', title: 'Kaydedilemedi', message: (e as Error).message })
      return false
    } finally {
      setBusy(false)
    }
  }

  if (error)
    return (
      <Alert color="red" variant="light" icon={<IconAlertCircle size={18} />} title="Çağrı yüklenemedi">
        {error}{' '}
        <Anchor component={Link} to="/cagrilar">
          Çağrılara dön
        </Anchor>
      </Alert>
    )
  if (!call) return <PageLoader />

  const isOpen = call.status === 'acik' && (!call.deadline || new Date(call.deadline) >= new Date(new Date().toDateString()))
  return (
    <>
      <Group gap={6} mb={10}>
        <Anchor component={Link} to="/cagrilar" size="sm" c="dimmed">
          Açık çağrılar
        </Anchor>
        <Text size="sm" c="dimmed">
          / #{call.id}
        </Text>
      </Group>
      <Group justify="space-between" align="flex-end" mb="lg" wrap="wrap">
        <div style={{ minWidth: 0 }}>
          <Title order={1} className="app-display">
            {call.title}
          </Title>
          <Group gap="xs" mt={6}>
            {callTag(call)}
            <Text size="sm" c="dimmed">
              {call.organization ?? 'Kurum adı gizli'} · {timeAgo(call.created_at)} açıldı
            </Text>
          </Group>
        </div>
        {!isStartup && (
          <Group gap="xs">
            <Button component={Link} to={`/ihtiyaclar/${call.brief_id}`} variant="default">
              İhtiyaca git
            </Button>
            <Button
              variant="default"
              loading={busy}
              onClick={() =>
                run(
                  () => api.setCallStatus(call.id, call.status === 'acik' ? 'kapali' : 'acik'),
                  call.status === 'acik' ? 'Çağrı kapatıldı' : 'Çağrı yeniden açıldı',
                )
              }
            >
              {call.status === 'acik' ? 'Çağrıyı kapat' : 'Yeniden aç'}
            </Button>
          </Group>
        )}
      </Group>

      <Grid gap="lg">
        <Grid.Col span={{ base: 12, md: 5 }}>
          <SectionCard title="Çağrı metni">
            <Stack gap="md">
              <Text size="sm" style={{ whiteSpace: 'pre-line' }} lh={1.6}>
                {call.summary}
              </Text>
              {call.required_capabilities.length > 0 && (
                <MetaItem label="Aranan yetkinlikler">{call.required_capabilities.join(' · ')}</MetaItem>
              )}
              <Group gap="xl">
                {call.sector && <MetaItem label="Sektör">{call.sector}</MetaItem>}
                <MetaItem label="Son başvuru">{call.deadline ? formatDate(call.deadline) : 'Belirtilmedi'}</MetaItem>
              </Group>
              {!isStartup && call.hide_organization && (
                <Text size="xs" c="dimmed">
                  Kurum adı girişimlere gösterilmiyor.
                </Text>
              )}
            </Stack>
          </SectionCard>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 7 }}>
          {isStartup ? (
            call.my_application ? (
              <Stack gap="md">
                <Text className="app-section-title">Başvurunuz</Text>
                <ApplicationCard app={call.my_application} onOpen={setDrawer} />
              </Stack>
            ) : isOpen ? (
              <SectionCard title="Başvur" description={`${me?.startup?.name} adına`}>
                <Stack>
                  <Textarea
                    label="Bu problemi nasıl çözersiniz?"
                    description="Hazır ürününüzü, benzer bir referansınızı ve kurulum süresini yazın. Kurum başvuruyu bu metinle değerlendirir."
                    autosize
                    minRows={5}
                    value={note}
                    onChange={(e) => setNote(e.currentTarget.value)}
                  />
                  <Group justify="flex-end">
                    <Button
                      loading={busy}
                      disabled={note.trim().length < 20}
                      onClick={() => run(() => api.apply(call.id, note.trim()), 'Başvurunuz iletildi')}
                    >
                      Başvuruyu gönder
                    </Button>
                  </Group>
                </Stack>
              </SectionCard>
            ) : (
              <EmptyState title="Başvuruya kapalı" description="Bu çağrının süresi doldu ya da kurum çağrıyı kapattı." />
            )
          ) : call.applications.length === 0 ? (
            <EmptyState title="Henüz başvuru yok" description="Doğrulanmış girişimler başvurdukça burada görünür." />
          ) : (
            <Stack gap="md">
              <Text className="app-section-title">{call.applications.length} başvuru</Text>
              {call.applications.map((a) => (
                <ApplicationCard key={a.id} app={a} onOpen={setDrawer} onDecide={(app, decision) => setDeciding({ app, decision })} />
              ))}
            </Stack>
          )}
        </Grid.Col>
      </Grid>

      <StartupDrawer startup={drawer} onClose={() => setDrawer(null)} />
      <Modal
        opened={deciding !== null}
        onClose={() => setDeciding(null)}
        title={<Text fw={600}>{deciding?.app.startup.name}: {deciding?.decision === 'kabul' ? 'kabul et' : 'olumsuz'}</Text>}
      >
        <Stack>
          {deciding?.decision === 'kabul' && (
            <Text size="sm" c="dimmed">
              Girişim başvurarak ilgisini zaten bildirdi; kabul ettiğinizde pilot kartı iki taraf için de açılır.
            </Text>
          )}
          <Textarea
            label="Girişime not (isteğe bağlı)"
            autosize
            minRows={3}
            value={decisionNote}
            onChange={(e) => setDecisionNote(e.currentTarget.value)}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeciding(null)}>
              Vazgeç
            </Button>
            <Button
              color={deciding?.decision === 'ret' ? 'red' : undefined}
              loading={busy}
              onClick={async () => {
                if (!deciding) return
                const ok = await run(
                  () => api.decideApplication(deciding.app.id, deciding.decision, decisionNote.trim() || undefined),
                  deciding.decision === 'kabul' ? 'Pilot açıldı' : 'Başvuru sonuçlandı',
                )
                if (ok) {
                  setDeciding(null)
                  setDecisionNote('')
                }
              }}
            >
              {deciding?.decision === 'kabul' ? 'Kabul et' : 'Olumsuz'}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  )
}
