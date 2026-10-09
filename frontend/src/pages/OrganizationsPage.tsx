import { Anchor, Card, Group, MultiSelect, SimpleGrid, Stack, Text, TextInput } from '@mantine/core'
import { IconExternalLink, IconMapPin, IconSearch, IconSpeakerphone, IconUsers } from '@tabler/icons-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api'
import { EmptyState, OrgAvatar, PageHeader, PageLoader, Tag } from '../components/ui'
import { formatDate, TAG_COLOR, trFilter, trLower } from '../labels'
import type { OrganizationCard } from '../types'

const sortTr = (values: Iterable<string>) => [...new Set(values)].sort((a, b) => a.localeCompare(b, 'tr'))
const SIZE_LABEL: Record<string, string> = { '1-49': '1–49 çalışan', '50-249': '50–249 çalışan', '250-999': '250–999 çalışan', '1000+': '1000+ çalışan' }

function OrgCard({ org }: { org: OrganizationCard }) {
  const site = org.website?.replace(/^https?:\/\//, '').replace(/\/$/, '')
  return (
    <Card h="100%">
      <Stack gap="sm" h="100%">
        <Group gap="sm" wrap="nowrap" align="flex-start">
          <OrgAvatar name={org.name} size={42} />
          <div style={{ minWidth: 0 }}>
            <Text className="app-display" fz={22} lh={1.15}>
              {org.name}
            </Text>
            <Group gap={10} mt={4}>
              {org.sector && <Tag color={TAG_COLOR.slate}>{org.sector}</Tag>}
              {org.city && (
                <Group gap={3}>
                  <IconMapPin size={13} color="var(--app-muted)" />
                  <Text size="xs" c="dimmed">
                    {org.city}
                  </Text>
                </Group>
              )}
              {org.employee_range && (
                <Group gap={3}>
                  <IconUsers size={13} color="var(--app-muted)" />
                  <Text size="xs" c="dimmed">
                    {SIZE_LABEL[org.employee_range] ?? org.employee_range}
                  </Text>
                </Group>
              )}
            </Group>
          </div>
        </Group>

        <Text size="sm" c={org.description ? undefined : 'dimmed'} lh={1.55}>
          {org.description ?? 'Kurum henüz kendini tanıtmadı.'}
        </Text>

        {org.open_calls.length > 0 && (
          <div className="app-evidence">
            <Group gap={6} mb={4}>
              <IconSpeakerphone size={14} />
              <Text size="xs" fw={600}>
                Açık çağrıları
              </Text>
            </Group>
            <Stack gap={2}>
              {org.open_calls.map((c) => (
                <Anchor key={c.id} component={Link} to={`/cagrilar/${c.id}`} size="sm">
                  {c.title}
                  {c.deadline ? (
                    <Text span size="xs" c="dimmed">
                      {' '}
                      · son başvuru {formatDate(c.deadline)}
                    </Text>
                  ) : null}
                </Anchor>
              ))}
            </Stack>
          </div>
        )}

        <Group justify="space-between" mt="auto">
          {site ? (
            <Anchor href={org.website!} target="_blank" rel="noreferrer" size="xs">
              <Group gap={4}>
                {site}
                <IconExternalLink size={12} />
              </Group>
            </Anchor>
          ) : (
            <span />
          )}
          {org.joined_at && (
            <Text size="xs" c="dimmed">
              {formatDate(org.joined_at)} tarihinden beri Needle’da
            </Text>
          )}
        </Group>
      </Stack>
    </Card>
  )
}

// Talep tarafının vitrini: girişimler hangi kurumların platformda olduğunu ve ne iş yaptıklarını görür
export default function OrganizationsPage() {
  const [orgs, setOrgs] = useState<OrganizationCard[] | null>(null)
  const [query, setQuery] = useState('')
  const [sectors, setSectors] = useState<string[]>([])
  const [cities, setCities] = useState<string[]>([])

  useEffect(() => {
    api.organizations().then(setOrgs).catch(() => setOrgs([]))
  }, [])

  const shown = useMemo(() => {
    const q = trLower(query.trim())
    return (orgs ?? []).filter(
      (o) =>
        (!sectors.length || (o.sector && sectors.includes(o.sector))) &&
        (!cities.length || (o.city && cities.includes(o.city))) &&
        (!q || trLower([o.name, o.description ?? '', o.sector ?? '', ...o.open_calls.map((c) => c.title)].join(' ')).includes(q)),
    )
  }, [orgs, query, sectors, cities])

  if (!orgs) return <PageLoader />

  return (
    <>
      <PageHeader
        title="Kurumlar"
        description="Needle’da çözüm arayan kurumlar: ne iş yaptıkları, nerede oldukları ve girişimlere açık çağrıları. Kurumların ihtiyaçları ve eşleştirme ayarları burada görünmez."
      />
      <Card padding="md" mb="md">
        <Group gap="sm" wrap="wrap">
          <TextInput
            leftSection={<IconSearch size={16} />}
            placeholder="Ad, sektör veya tanıtımda ara"
            value={query}
            onChange={(e) => setQuery(e.currentTarget.value)}
            style={{ flex: 1, minWidth: 220 }}
          />
          <MultiSelect
            placeholder={sectors.length ? undefined : 'Sektör'}
            data={sortTr(orgs.map((o) => o.sector).filter((s): s is string => !!s))}
            value={sectors}
            onChange={setSectors}
            searchable
            filter={trFilter}
            clearable
            w={220}
          />
          <MultiSelect
            placeholder={cities.length ? undefined : 'Şehir'}
            data={sortTr(orgs.map((o) => o.city).filter((s): s is string => !!s))}
            value={cities}
            onChange={setCities}
            searchable
            filter={trFilter}
            clearable
            w={180}
          />
        </Group>
      </Card>
      {shown.length === 0 ? (
        <EmptyState
          title={orgs.length ? 'Sonuç yok' : 'Henüz kurum yok'}
          description={orgs.length ? 'Aramayı ya da filtreleri değiştirin.' : 'Kurumlar profillerini tamamladıkça burada görünür.'}
        />
      ) : (
        <>
          <Text size="sm" c="dimmed" mb="sm">
            {shown.length} kurum
          </Text>
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
            {shown.map((o) => (
              <OrgCard key={o.id} org={o} />
            ))}
          </SimpleGrid>
        </>
      )}
    </>
  )
}
