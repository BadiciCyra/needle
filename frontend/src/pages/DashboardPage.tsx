import { Anchor, Box, Button, Grid, Group, Progress, Stack, Table, Text, UnstyledButton } from '@mantine/core'
import { IconArrowUpRight, IconPlus } from '@tabler/icons-react'
import { useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { EmptyState, OrgAvatar, PageHeader, PageLoader, SectionCard, StageBadge, StatStrip, Tag } from '../components/ui'
import { useAppData } from '../data'
import { stageOf, TAG_COLOR, timeAgo } from '../labels'

interface Attention {
  key: string
  color: string
  kind: string
  title: string
  to: string
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const { needs, pilots, startups } = useAppData()

  const stats = useMemo(() => {
    if (!needs || !pilots) return null
    const stages = needs.map(stageOf)
    const count = (s: string) => stages.filter((x) => x === s).length
    return {
      total: needs.length,
      open: needs.length - count('pilot'),
      followup: count('followup'),
      ready: count('ready'),
      review: count('review'),
      briefed: needs.length - count('followup'),
      matched: count('review') + count('pilot'),
      piloted: count('pilot'),
      activePilots: pilots.filter((p) => p.status === 'active').length,
      stalePilots: pilots.filter((p) => p.stale),
      donePilots: pilots.filter((p) => p.status === 'done').length,
    }
  }, [needs, pilots])

  const sectors = useMemo(() => {
    const counts = new Map<string, number>()
    startups?.forEach((s) => counts.set(s.sector, (counts.get(s.sector) ?? 0) + 1))
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8)
  }, [startups])

  if (!stats || !needs) return <PageLoader />

  const funnel = [
    { label: 'İhtiyaç girildi', value: stats.total },
    { label: 'Brief tamamlandı', value: stats.briefed },
    { label: 'Kısa liste çıktı', value: stats.matched },
    { label: 'Pilota dönüştü', value: stats.piloted },
    { label: 'Pilot tamamlandı', value: stats.donePilots },
  ]

  const attention: Attention[] = [
    ...stats.stalePilots.map((p) => ({
      key: `stale-${p.id}`,
      color: TAG_COLOR.red,
      kind: `${p.days_inactive} gün hareketsiz`,
      title: `${p.startup.name} — ${p.brief_title}`,
      to: '/pilotlar',
    })),
    ...needs
      .filter((n) => stageOf(n) === 'review')
      .map((n) => ({ key: `r-${n.brief_id}`, color: TAG_COLOR.thread, kind: `${n.shortlist_count} aday karar bekliyor`, title: n.title, to: `/ihtiyaclar/${n.brief_id}` })),
    ...needs
      .filter((n) => stageOf(n) === 'followup')
      .map((n) => ({ key: `f-${n.brief_id}`, color: TAG_COLOR.ochre, kind: 'Takip soruları cevapsız', title: n.title, to: `/ihtiyaclar/${n.brief_id}` })),
    ...needs
      .filter((n) => stageOf(n) === 'ready')
      .map((n) => ({ key: `m-${n.brief_id}`, color: TAG_COLOR.slate, kind: 'Eşleştirme yapılmadı', title: n.title, to: `/ihtiyaclar/${n.brief_id}` })),
  ]

  const today = new Date().toLocaleDateString('tr-TR', { weekday: 'long', day: 'numeric', month: 'long' })

  return (
    <>
      <PageHeader
        eyebrow={today}
        title="Genel bakış"
        description="Kurum ihtiyaçlarından gerekçeli eşleşmelere ve pilotlara kadar sürecin durumu."
        actions={
          <Button component={Link} to="/ihtiyaclar/yeni" leftSection={<IconPlus size={15} />}>
            Yeni ihtiyaç
          </Button>
        }
      />

      <StatStrip
        items={[
          {
            label: 'Açık ihtiyaç',
            value: stats.open,
            hint: `${stats.followup} bilgi bekliyor · ${stats.ready} eşleştirmeye hazır`,
            onClick: () => navigate('/ihtiyaclar'),
          },
          { label: 'Karar bekleyen', value: stats.review, hint: 'Kısa listesi hazır ihtiyaçlar', onClick: () => navigate('/ihtiyaclar?asama=review') },
          {
            label: 'Aktif pilot',
            value: stats.activePilots,
            hint: stats.stalePilots.length ? `${stats.stalePilots.length} tanesi hareketsiz` : 'Hepsi hareketli',
            tone: stats.stalePilots.length ? 'alert' : undefined,
            onClick: () => navigate('/pilotlar'),
          },
          {
            label: 'Girişim havuzu',
            value: startups?.length ?? '—',
            hint: `${new Set(startups?.map((s) => s.sector)).size} sektör · ${new Set(startups?.map((s) => s.location)).size} şehir`,
            onClick: () => navigate('/ekosistem'),
          },
        ]}
      />

      {stats.total === 0 ? (
        <EmptyState
          title="İlk ihtiyacı girin"
          description="Kurumun ihtiyacını kendi cümleleriyle yazın; Needle onu brief’e çevirip uygun girişimleri gerekçeleriyle bulsun."
          action={
            <Button component={Link} to="/ihtiyaclar/yeni" leftSection={<IconPlus size={15} />}>
              Yeni ihtiyaç
            </Button>
          }
        />
      ) : (
        <Grid gap="lg">
          <Grid.Col span={{ base: 12, md: 7 }}>
            <Stack gap="lg">
              <SectionCard title="Yapılacaklar" description={attention.length ? `${attention.length} açık iş` : 'Bekleyen iş yok'} padding="0">
                {attention.length === 0 ? (
                  <Text size="sm" c="var(--app-muted)" p="lg">
                    Şu an sizden bir karar ya da bilgi bekleyen ihtiyaç veya pilot yok.
                  </Text>
                ) : (
                  attention.slice(0, 8).map((a) => (
                    <UnstyledButton key={a.key} component={Link} to={a.to} display="block" px="lg" py={12} className="app-list-row">
                      <Group justify="space-between" wrap="nowrap" gap="md">
                        <div style={{ minWidth: 0 }}>
                          <Tag color={a.color}>
                            <Text span size="xs" c="var(--app-muted)">
                              {a.kind}
                            </Text>
                          </Tag>
                          <Text size="sm" mt={4} truncate>
                            {a.title}
                          </Text>
                        </div>
                        <IconArrowUpRight size={16} stroke={1.5} color="var(--app-muted)" style={{ flexShrink: 0 }} />
                      </Group>
                    </UnstyledButton>
                  ))
                )}
              </SectionCard>

              <SectionCard
                title="Son ihtiyaçlar"
                action={
                  <Anchor component={Link} to="/ihtiyaclar" size="xs" c="var(--app-ink)" td="underline">
                    Tümünü gör
                  </Anchor>
                }
                padding="0"
              >
                <Table>
                  <Table.Tbody>
                    {needs.slice(0, 6).map((n) => (
                      <Table.Tr key={n.brief_id} className="app-row-link" onClick={() => navigate(`/ihtiyaclar/${n.brief_id}`)}>
                        <Table.Td pl="lg">
                          <Group gap="sm" wrap="nowrap">
                            <OrgAvatar name={n.organization ?? n.title} size={30} />
                            <div style={{ minWidth: 0 }}>
                              <Text size="sm" fw={500} lineClamp={1}>
                                {n.title}
                              </Text>
                              <Text size="xs" c="var(--app-muted)" lineClamp={1}>
                                {n.organization ?? 'Kurum belirtilmedi'}
                              </Text>
                            </div>
                          </Group>
                        </Table.Td>
                        <Table.Td>
                          <StageBadge stage={stageOf(n)} />
                        </Table.Td>
                        <Table.Td pr="lg" ta="right">
                          <Text size="xs" c="var(--app-muted)" className="app-num" style={{ whiteSpace: 'nowrap' }}>
                            {timeAgo(n.created_at)}
                          </Text>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </SectionCard>
            </Stack>
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 5 }}>
            <Stack gap="lg">
              <SectionCard title="Süreç" description="İhtiyaçların pilota dönüşme oranı">
                <Stack gap={14}>
                  {funnel.map((step, i) => {
                    const pct = stats.total ? (step.value / stats.total) * 100 : 0
                    return (
                      <div key={step.label}>
                        <Group justify="space-between" mb={6} wrap="nowrap">
                          <Text size="sm">
                            <Text span className="app-num" c="var(--app-muted)" size="xs" mr={10}>
                              {String(i + 1).padStart(2, '0')}
                            </Text>
                            {step.label}
                          </Text>
                          <Text size="sm" className="app-num">
                            {step.value}
                            <Text span c="var(--app-muted)" size="xs" ml={8}>
                              {Math.round(pct)}%
                            </Text>
                          </Text>
                        </Group>
                        <Progress value={pct} color={i === funnel.length - 1 ? 'thread.6' : 'ink'} />
                      </div>
                    )
                  })}
                </Stack>
              </SectionCard>

              <SectionCard
                title="Ekosistem"
                description="Girişim havuzunun sektör dağılımı"
                action={
                  <Anchor component={Link} to="/ekosistem" size="xs" c="var(--app-ink)" td="underline">
                    Keşfet
                  </Anchor>
                }
              >
                <Stack gap={10}>
                  {sectors.map(([sector, n]) => (
                    <Group key={sector} gap="sm" wrap="nowrap">
                      <Text size="sm" w={130} truncate>
                        {sector}
                      </Text>
                      <Box style={{ flex: 1 }}>
                        <Progress value={(n / sectors[0]![1]) * 100} color="gray.5" />
                      </Box>
                      <Text size="xs" className="app-num" c="var(--app-muted)" w={24} ta="right">
                        {n}
                      </Text>
                    </Group>
                  ))}
                </Stack>
              </SectionCard>
            </Stack>
          </Grid.Col>
        </Grid>
      )}
    </>
  )
}
