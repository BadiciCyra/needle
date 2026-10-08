import { Anchor, Button, Grid, Group, Stack, Text, UnstyledButton } from '@mantine/core'
import { Link } from 'react-router-dom'

import { useAuth } from '../auth'
import { PageHeader, PageLoader, SectionCard, StatStrip, Tag } from '../components/ui'
import { useAppData } from '../data'
import { TAG_COLOR, timeAgo } from '../labels'

// Girişimin genel bakışı: bekleyen davetler, başvurulabilir çağrılar, süren pilotlar
export default function StartupHomePage() {
  const { me } = useAuth()
  const { introductions, calls, pilots } = useAppData()
  if (!introductions || !calls || !pilots) return <PageLoader />

  const waiting = introductions.filter((i) => i.status === 'bekliyor')
  const openCalls = calls.filter((c) => c.status === 'acik' && !c.my_application)
  const active = pilots.filter((p) => p.status === 'active')

  return (
    <>
      <PageHeader
        eyebrow="Girişim"
        title={me?.startup?.name ?? 'Genel bakış'}
        description="Kurumlardan gelen tanıştırma istekleri, başvurabileceğiniz açık çağrılar ve süren pilotlarınız."
        actions={
          <Button component={Link} to="/profil" variant="default">
            Profili düzenle
          </Button>
        }
      />
      <StatStrip
        items={[
          { label: 'Bekleyen davet', value: waiting.length, tone: waiting.length ? 'alert' : undefined },
          { label: 'Açık çağrı', value: openCalls.length },
          { label: 'Aktif pilot', value: active.length },
        ]}
      />
      <Grid gap="lg">
        <Grid.Col span={{ base: 12, md: 6 }}>
          <SectionCard
            title="Tanıştırma istekleri"
            action={
              <Anchor component={Link} to="/tanistirmalar" size="sm">
                Tümü
              </Anchor>
            }
            padding="0"
          >
            {waiting.length === 0 ? (
              <Text size="sm" c="dimmed" p="lg">
                Bekleyen istek yok. Kurumlar ihtiyaçları için sizi seçtiğinde burada görünür.
              </Text>
            ) : (
              waiting.map((i) => (
                <UnstyledButton key={i.id} component={Link} to="/tanistirmalar" className="app-list-row" display="block" px="lg" py="sm">
                  <Text fw={500}>{i.brief.title}</Text>
                  <Text size="xs" c="dimmed">
                    {i.organization ?? 'Kurum'} · {timeAgo(i.created_at)}
                  </Text>
                </UnstyledButton>
              ))
            )}
          </SectionCard>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <SectionCard
            title="Açık çağrılar"
            action={
              <Anchor component={Link} to="/cagrilar" size="sm">
                Tümü
              </Anchor>
            }
            padding="0"
          >
            {openCalls.length === 0 ? (
              <Text size="sm" c="dimmed" p="lg">
                Şu an başvurulabilir çağrı yok.
              </Text>
            ) : (
              openCalls.slice(0, 6).map((c) => (
                <UnstyledButton key={c.id} component={Link} to={`/cagrilar/${c.id}`} className="app-list-row" display="block" px="lg" py="sm">
                  <Group justify="space-between" wrap="nowrap">
                    <Stack gap={0} style={{ minWidth: 0 }}>
                      <Text fw={500} truncate>
                        {c.title}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {c.organization ?? 'Kurum adı gizli'} · {timeAgo(c.created_at)}
                      </Text>
                    </Stack>
                    {c.sector && <Tag color={TAG_COLOR.slate}>{c.sector}</Tag>}
                  </Group>
                </UnstyledButton>
              ))
            )}
          </SectionCard>
        </Grid.Col>
      </Grid>
    </>
  )
}
