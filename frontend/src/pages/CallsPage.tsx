import { Anchor, Card, Group, SegmentedControl, SimpleGrid, Stack, Text, UnstyledButton } from '@mantine/core'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '../auth'
import { EmptyState, PageHeader, PageLoader, Tag } from '../components/ui'
import { useAppData } from '../data'
import { formatDate, TAG_COLOR, timeAgo } from '../labels'
import type { OpenCall } from '../types'

export function callTag(call: OpenCall) {
  if (call.my_application) {
    const s = call.my_application.status
    return s === 'kabul' ? (
      <Tag color={TAG_COLOR.green}>Başvurunuz kabul edildi</Tag>
    ) : s === 'ret' ? (
      <Tag color={TAG_COLOR.gray}>Başvurunuz olumsuz</Tag>
    ) : (
      <Tag color={TAG_COLOR.ochre}>Başvurdunuz</Tag>
    )
  }
  return call.status === 'acik' ? <Tag color={TAG_COLOR.thread}>Başvuruya açık</Tag> : <Tag color={TAG_COLOR.gray}>Kapalı</Tag>
}

function CallCard({ call }: { call: OpenCall }) {
  const { isStartup } = useAuth()
  return (
    <UnstyledButton component={Link} to={`/cagrilar/${call.id}`} style={{ display: 'block' }}>
      <Card h="100%" className="app-hover-card">
        <Stack gap="sm" h="100%">
          <Group justify="space-between" wrap="nowrap" align="flex-start">
            <Text className="app-display" fz={22} lh={1.2}>
              {call.title}
            </Text>
            {callTag(call)}
          </Group>
          <Text size="sm" c="dimmed" lineClamp={3} style={{ whiteSpace: 'pre-line' }}>
            {call.summary}
          </Text>
          <Group gap="xs" mt="auto">
            {call.required_capabilities.slice(0, 3).map((c) => (
              <Tag key={c} color={TAG_COLOR.slate}>
                {c}
              </Tag>
            ))}
          </Group>
          <Text size="xs" c="dimmed">
            {call.organization ?? 'Kurum adı gizli'} · {timeAgo(call.created_at)}
            {call.deadline ? ` · son başvuru ${formatDate(call.deadline)}` : ''}
            {!isStartup ? ` · ${call.application_count} başvuru` : ''}
          </Text>
        </Stack>
      </Card>
    </UnstyledButton>
  )
}

export default function CallsPage() {
  const { calls } = useAppData()
  const { isStartup } = useAuth()
  const [filter, setFilter] = useState<'acik' | 'tumu'>('acik')
  const shown = useMemo(
    () => calls?.filter((c) => filter === 'tumu' || (c.status === 'acik' && !(isStartup && c.my_application))) ?? [],
    [calls, filter, isStartup],
  )
  if (!calls) return <PageLoader />

  return (
    <>
      <PageHeader
        title="Açık çağrılar"
        description={
          isStartup
            ? 'Kurumların havuzda çözüm bulamadığı ihtiyaçlar. Çözümünüz uyuyorsa nasıl çözeceğinizi yazarak başvurun.'
            : 'Havuzda doğrudan çözen girişim bulunamayan ihtiyaçlar girişimlere duyurulur. Çağrı, ihtiyacın eşleştirme sonucundan açılır.'
        }
      />
      <SegmentedControl
        mb="md"
        value={filter}
        onChange={(v) => setFilter(v as 'acik' | 'tumu')}
        data={[
          { value: 'acik', label: isStartup ? 'Başvurulabilir' : 'Açık' },
          { value: 'tumu', label: isStartup ? 'Tümü (başvurduklarım dahil)' : 'Tümü' },
        ]}
      />
      {shown.length === 0 ? (
        <EmptyState
          title="Çağrı yok"
          description={
            isStartup ? (
              'Şu an başvurulabilir çağrı yok. Yeni çağrılar açıldıkça burada görünecek.'
            ) : (
              <>
                Eşleştirmede “güçlü eşleşme yok” çıkan bir ihtiyacı çağrıya çevirebilirsiniz.{' '}
                <Anchor component={Link} to="/ihtiyaclar">
                  İhtiyaçlara git
                </Anchor>
              </>
            )
          }
        />
      ) : (
        <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
          {shown.map((c) => (
            <CallCard key={c.id} call={c} />
          ))}
        </SimpleGrid>
      )}
    </>
  )
}
