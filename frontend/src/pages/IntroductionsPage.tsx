import { Anchor, Button, Card, Group, Modal, SegmentedControl, Stack, Text, Textarea } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconCheck, IconX } from '@tabler/icons-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api'
import IntroEmailDraft from '../components/IntroEmailDraft'
import { useAuth } from '../auth'
import { EmptyState, MetaItem, OrgAvatar, PageHeader, PageLoader, Tag } from '../components/ui'
import { useAppData } from '../data'
import { INTRO_STATUS, timeAgo } from '../labels'
import type { Introduction } from '../types'

const STARTUP_VIEW = { bekliyor: 'Cevabınız bekleniyor', kabul: 'Kabul ettiniz', ret: 'Reddettiniz' }

function IntroCard({
  intro,
  onRespond,
  onChange,
}: {
  intro: Introduction
  onRespond?: (i: Introduction, d: 'kabul' | 'ret') => void
  onChange: (i: Introduction) => void
}) {
  const { isStartup, isAdmin } = useAuth()
  const status = isStartup ? { ...INTRO_STATUS[intro.status], label: STARTUP_VIEW[intro.status] } : INTRO_STATUS[intro.status]
  const b = intro.brief
  const counterpart = isStartup ? intro.organization ?? 'Kurum' : intro.startup.name
  return (
    <Card>
      <Stack gap="md">
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
            <OrgAvatar name={counterpart} size={42} />
            <div style={{ minWidth: 0 }}>
              <Text className="app-display" fz={24} lh={1.15}>
                {isStartup ? b.title : counterpart}
              </Text>
              <Text size="sm" c="dimmed">
                {isStartup ? counterpart : b.title}
                {isAdmin && intro.organization ? ` · ${intro.organization}` : ''} · {timeAgo(intro.created_at)}
                {intro.source === 'cagri' ? ' · açık çağrıdan' : intro.source === 'havuz' ? ' · havuzdan' : ''}
              </Text>
            </div>
          </Group>
          <Tag color={status.color}>{status.label}</Tag>
        </Group>

        {isStartup && (
          <Stack gap="xs">
            {b.problem && <MetaItem label="Problem">{b.problem}</MetaItem>}
            {b.scope && <MetaItem label="Kapsam">{b.scope}</MetaItem>}
            {b.required_capabilities.length > 0 && (
              <MetaItem label="Aranan yetkinlikler">{b.required_capabilities.join(' · ')}</MetaItem>
            )}
            <Group gap="xl">
              {b.success_criteria && <MetaItem label="Başarı kriteri">{b.success_criteria}</MetaItem>}
              {b.timeline && <MetaItem label="Süre">{b.timeline}</MetaItem>}
            </Group>
          </Stack>
        )}

        {intro.firm_note && (
          <div className="app-evidence">
            <Text size="xs" c="dimmed">
              Kurumun notu
            </Text>
            <Text size="sm">{intro.firm_note}</Text>
          </div>
        )}
        {intro.startup_note && (
          <div className="app-evidence">
            <Text size="xs" c="dimmed">
              {intro.responded_by === 'yonetici' ? 'Program yöneticisinin notu (girişim adına)' : 'Girişimin notu'}
            </Text>
            <Text size="sm">{intro.startup_note}</Text>
          </div>
        )}

        {!isStartup && !intro.startup_has_account && (intro.email || intro.status === 'bekliyor') && (
          <IntroEmailDraft intro={intro} onChange={onChange} />
        )}

        <Group justify="flex-end" gap="xs">
          {intro.pilot_id && (
            <Button component={Link} to="/pilotlar" size="xs" variant="default">
              Pilota git
            </Button>
          )}
          {intro.status === 'bekliyor' && onRespond && (
            <>
              <Button variant="default" size="xs" leftSection={<IconX size={14} />} onClick={() => onRespond(intro, 'ret')}>
                {isAdmin ? 'Girişim adına reddet' : 'Reddet'}
              </Button>
              <Button size="xs" leftSection={<IconCheck size={14} />} onClick={() => onRespond(intro, 'kabul')}>
                {isAdmin ? 'Girişim adına kabul et' : 'Kabul et ve pilotu başlat'}
              </Button>
            </>
          )}
        </Group>
      </Stack>
    </Card>
  )
}

export default function IntroductionsPage() {
  const { introductions, refresh } = useAppData()
  const { isStartup, isAdmin } = useAuth()
  const [filter, setFilter] = useState<'bekliyor' | 'tumu'>('bekliyor')
  const [responding, setResponding] = useState<{ intro: Introduction; decision: 'kabul' | 'ret' } | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const shown = useMemo(
    () => introductions?.filter((i) => filter === 'tumu' || i.status === 'bekliyor') ?? [],
    [introductions, filter],
  )
  if (!introductions) return <PageLoader />

  const respond = async () => {
    if (!responding) return
    setBusy(true)
    try {
      await api.respondIntroduction(responding.intro.id, responding.decision, note.trim() || undefined)
      await refresh()
      notifications.show({
        color: 'teal',
        message: responding.decision === 'kabul' ? 'Tanıştırma kabul edildi, pilot açıldı.' : 'Cevabınız kuruma iletildi.',
      })
      setResponding(null)
      setNote('')
    } catch (e) {
      notifications.show({ color: 'red', title: 'Kaydedilemedi', message: (e as Error).message })
    } finally {
      setBusy(false)
    }
  }

  const canRespond = isStartup || isAdmin
  return (
    <>
      <PageHeader
        title="Tanıştırmalar"
        description={
          isStartup
            ? 'Kurumlar ihtiyaçları için sizi seçtiğinde istek buraya düşer. Kabul ederseniz pilot kartı iki taraf için de açılır.'
            : isAdmin
              ? 'Kurumların seçtiği girişimlere giden istekler. Hesabı olmayan girişimlerle görüşüp sonucu onların adına işleyin.'
              : 'Kabul ettiğiniz adaylara ve havuzdan seçtiğiniz girişimlere giden tanıştırma istekleri. Girişim kabul edince pilot kartı açılır.'
        }
      />
      <SegmentedControl
        mb="md"
        value={filter}
        onChange={(v) => setFilter(v as 'bekliyor' | 'tumu')}
        data={[
          { value: 'bekliyor', label: `Bekleyen (${introductions.filter((i) => i.status === 'bekliyor').length})` },
          { value: 'tumu', label: 'Tümü' },
        ]}
      />
      {shown.length === 0 ? (
        <EmptyState
          title={filter === 'bekliyor' ? 'Bekleyen istek yok' : 'Henüz tanıştırma yok'}
          description={
            isStartup ? (
              <>
                Bu arada{' '}
                <Anchor component={Link} to="/cagrilar">
                  açık çağrılara
                </Anchor>{' '}
                göz atabilirsiniz.
              </>
            ) : (
              'Bir ihtiyacın eşleştirme sonucunda adayı kabul ettiğinizde istek burada görünür.'
            )
          }
        />
      ) : (
        <Stack gap="md">
          {shown.map((intro) => (
            <IntroCard
              key={intro.id}
              intro={intro}
              onChange={() => refresh()}
              onRespond={canRespond ? (i, d) => setResponding({ intro: i, decision: d }) : undefined}
            />
          ))}
        </Stack>
      )}

      <Modal
        opened={responding !== null}
        onClose={() => setResponding(null)}
        title={<Text fw={600}>{responding?.decision === 'kabul' ? 'Tanıştırmayı kabul et' : 'Tanıştırmayı reddet'}</Text>}
      >
        <Stack>
          <Textarea
            label={responding?.decision === 'kabul' ? 'Kuruma not (isteğe bağlı)' : 'Sebep (isteğe bağlı)'}
            description={
              isAdmin
                ? 'Girişimle nasıl görüştüğünüzü yazın; kayıt "yönetici tarafından" olarak işaretlenir.'
                : responding?.decision === 'kabul'
                  ? 'İletişim için kişi ve e-posta yazabilirsiniz.'
                  : 'Örn. şu an kapasitemiz yok, bu alanda çalışmıyoruz…'
            }
            autosize
            minRows={3}
            value={note}
            onChange={(e) => setNote(e.currentTarget.value)}
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setResponding(null)}>
              Vazgeç
            </Button>
            <Button color={responding?.decision === 'ret' ? 'red' : undefined} loading={busy} onClick={respond}>
              {responding?.decision === 'kabul' ? 'Kabul et' : 'Reddet'}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  )
}
