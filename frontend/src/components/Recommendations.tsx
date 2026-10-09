import { Anchor, Button, Group, SimpleGrid, Stack, Text, UnstyledButton } from '@mantine/core'
import { type ReactNode, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api, ApiError } from '../api'
import { useAppData } from '../data'
import { formatDate, MATURITY_LABEL, TAG_COLOR } from '../labels'
import type { OrganizationRecommendations, StartupProfile, StartupRecommendations } from '../types'
import StartupDrawer from './StartupDrawer'
import { OrgAvatar, SectionCard, Tag } from './ui'

type Load<T> = { data: T } | { missing: string } | null

function useRecommendations<T>(fetcher: () => Promise<T>): Load<T> {
  const [state, setState] = useState<Load<T>>(null)
  useEffect(() => {
    let alive = true
    fetcher()
      .then((data) => alive && setState({ data }))
      .catch(
        (e) =>
          alive &&
          setState({
            missing: e instanceof ApiError && e.status === 409 ? e.message : 'Öneriler şu an yüklenemedi.',
          }),
      )
    return () => {
      alive = false
    }
  }, [fetcher])
  return state
}

const Muted = ({ children }: { children: ReactNode }) => (
  <Text size="sm" c="dimmed" p="lg">
    {children}
  </Text>
)

export function StartupRecommendationsSection() {
  const state = useRecommendations<StartupRecommendations>(api.startupRecommendations)
  if (state === null) return null
  if ('missing' in state)
    return (
      <SectionCard title="Size uygun" description="Profilinize göre kurumlar, çağrılar ve talep sinyalleri">
        <Stack gap="xs" align="flex-start">
          <Text size="sm" c="dimmed">
            {state.missing}
          </Text>
          <Button size="xs" variant="default" component={Link} to="/profil-bagla">
            Profilimi bağla
          </Button>
        </Stack>
      </SectionCard>
    )

  const { calls, organizations, signals } = state.data
  return (
    <Stack gap="lg" mb="lg">
      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="lg">
        <SectionCard title="Size uygun çağrılar" description="Yetkinliklerinize en yakın açık çağrılar" padding="0">
          {calls.length === 0 ? (
            <Muted>Şu an açık çağrı yok.</Muted>
          ) : (
            calls.slice(0, 5).map((c) => (
              <UnstyledButton key={c.id} component={Link} to={`/cagrilar/${c.id}`} className="app-list-row" display="block" px="lg" py="sm">
                <Text fw={500} lineClamp={1}>
                  {c.title}
                </Text>
                <Text size="xs" c="dimmed">
                  {c.organization ?? 'Kurum adı gizli'}
                  {c.deadline ? ` · son gün ${formatDate(c.deadline)}` : ''}
                </Text>
                {c.reason && (
                  <Text size="xs" mt={4}>
                    {c.reason}
                  </Text>
                )}
              </UnstyledButton>
            ))
          )}
        </SectionCard>
        <SectionCard
          title="Size uygun kurumlar"
          description="Tanıtımı ve çağrıları işinize en yakın kurumlar"
          action={
            <Anchor component={Link} to="/kurumlar" size="sm">
              Tümü
            </Anchor>
          }
          padding="0"
        >
          {organizations.length === 0 ? (
            <Muted>Henüz tanıtımını yazmış kurum yok.</Muted>
          ) : (
            organizations.slice(0, 5).map((o) => (
              <UnstyledButton key={o.id} component={Link} to="/kurumlar" className="app-list-row" display="block" px="lg" py="sm">
                <Group gap="sm" wrap="nowrap">
                  <OrgAvatar name={o.name} size={28} />
                  <div style={{ minWidth: 0 }}>
                    <Text fw={500} truncate>
                      {o.name}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {[o.sector, o.city].filter(Boolean).join(' · ') || 'Kurum'}
                      {o.open_calls ? ` · ${o.open_calls} açık çağrı` : ''}
                    </Text>
                  </div>
                </Group>
              </UnstyledButton>
            ))
          )}
        </SectionCard>
      </SimpleGrid>
      <SectionCard title="Talep sinyalleri" description="Son dört ayda birden fazla kurumun aradığı yetkinlikler; kurum adları gösterilmez">
        {signals.length === 0 ? (
          <Text size="sm" c="dimmed">
            Henüz birden fazla kurumun ortak aradığı bir yetkinlik oluşmadı.
          </Text>
        ) : (
          <Group gap="xs">
            {signals.map((s) => (
              <Tag key={s.capability} color={TAG_COLOR.thread} tooltip={s.variants.length > 1 ? s.variants.join(' · ') : undefined}>
                {s.capability}
                <Text span size="xs" c="dimmed" ml={6}>
                  {s.organizations} kurum
                </Text>
              </Tag>
            ))}
          </Group>
        )}
      </SectionCard>
    </Stack>
  )
}

export function OrganizationRecommendationsSection() {
  const state = useRecommendations<OrganizationRecommendations>(api.organizationRecommendations)
  const { startups } = useAppData()
  const [drawer, setDrawer] = useState<StartupProfile | null>(null)
  if (state === null) return null

  const description =
    'missing' in state || state.data.basis.length === 0
      ? 'Kurum tanıtımınıza göre havuzdaki en yakın girişimler'
      : `Aradığınız yetkinliklere göre: ${state.data.basis.slice(0, 4).join(', ')}`

  return (
    <SectionCard
      title="Size uygun girişimler"
      description={description}
      action={
        <Anchor component={Link} to="/ekosistem" size="xs" c="var(--app-ink)" td="underline">
          Havuz
        </Anchor>
      }
      padding="0"
    >
      {'missing' in state ? (
        <Stack gap="xs" align="flex-start" p="lg">
          <Text size="sm" c="dimmed">
            {state.missing}
          </Text>
          <Button size="xs" variant="default" component={Link} to="/profil">
            Kurum profilini düzenle
          </Button>
        </Stack>
      ) : (
        state.data.startups.slice(0, 6).map((s) => (
          <UnstyledButton key={s.id} className="app-list-row" display="block" w="100%" px="lg" py="sm" onClick={() => setDrawer(startups?.find((p) => p.id === s.id) ?? null)}>
            <Group justify="space-between" wrap="nowrap" gap="sm">
              <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
                <OrgAvatar name={s.name} size={28} />
                <div style={{ minWidth: 0 }}>
                  <Text size="sm" fw={500} truncate>
                    {s.name}
                  </Text>
                  <Text size="xs" c="dimmed" truncate>
                    {s.sector} · {MATURITY_LABEL[s.maturity]} · {s.location}
                  </Text>
                </div>
              </Group>
              <Group gap={4} wrap="nowrap" style={{ flexShrink: 0 }}>
                {s.applied && <Tag color={TAG_COLOR.thread}>Başvurdu</Tag>}
                {s.on_platform && <Tag color={TAG_COLOR.slate}>Platformda</Tag>}
              </Group>
            </Group>
            {s.reason && (
              <Text size="xs" mt={4} lineClamp={2}>
                {s.reason}
              </Text>
            )}
          </UnstyledButton>
        ))
      )}
      <StartupDrawer startup={drawer} onClose={() => setDrawer(null)} introduce />
    </SectionCard>
  )
}
