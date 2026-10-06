import { Badge, Card, Group, MultiSelect, SegmentedControl, SimpleGrid, Stack, Table, Text, TextInput } from '@mantine/core'
import { IconLayoutGrid, IconList, IconMapPin, IconSearch } from '@tabler/icons-react'
import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import StartupDrawer from '../components/StartupDrawer'
import { OrgAvatar, PageHeader, PageLoader } from '../components/ui'
import { useAppData } from '../data'
import { MATURITY_LABEL, MATURITY_ORDER } from '../labels'
import type { StartupProfile } from '../types'

const norm = (s: string) => s.toLocaleLowerCase('tr-TR')
const sortTr = (values: Iterable<string>) => [...new Set(values)].sort((a, b) => a.localeCompare(b, 'tr'))

function Capabilities({ items, max = 2 }: { items: string[]; max?: number }) {
  return (
    <Group gap={4} wrap="nowrap">
      {items.slice(0, max).map((c) => (
        <Badge key={c} fw={400} maw={190} style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {c}
        </Badge>
      ))}
      {items.length > max && (
        <Text size="xs" c="dimmed">
          +{items.length - max}
        </Text>
      )}
    </Group>
  )
}

export default function EcosystemPage() {
  const { startups } = useAppData()
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState('')
  const [sectors, setSectors] = useState<string[]>([])
  const [cities, setCities] = useState<string[]>([])
  const [maturities, setMaturities] = useState<string[]>([])
  const [view, setView] = useState('table')

  const selected = startups?.find((s) => s.id === params.get('girisim')) ?? null
  const open = (s: StartupProfile) => setParams({ girisim: s.id })

  const rows = useMemo(() => {
    const q = norm(query.trim())
    return (startups ?? []).filter(
      (s) =>
        (!sectors.length || sectors.includes(s.sector)) &&
        (!cities.length || cities.includes(s.location)) &&
        (!maturities.length || maturities.includes(s.maturity)) &&
        (!q || norm([s.name, s.description, s.sector, ...s.capabilities].join(' ')).includes(q)),
    )
  }, [startups, query, sectors, cities, maturities])

  if (!startups) return <PageLoader />

  return (
    <>
      <PageHeader
        title="Girişimler"
        description="Eşleştirmenin aradığı girişim havuzu. Yetkinlikler, girişimlerin kendi sitelerinden ve kamuya açık kaynaklardan derlendi."
      />

      <Card padding="md" mb="md">
        <Group gap="sm" wrap="wrap">
          <TextInput
            leftSection={<IconSearch size={16} />}
            placeholder="Ad, yetkinlik veya açıklamada ara"
            value={query}
            onChange={(e) => setQuery(e.currentTarget.value)}
            style={{ flex: '2 1 240px' }}
          />
          <MultiSelect
            placeholder={sectors.length ? undefined : 'Sektör'}
            data={sortTr(startups.map((s) => s.sector))}
            value={sectors}
            onChange={setSectors}
            clearable
            searchable
            style={{ flex: '1 1 160px' }}
          />
          <MultiSelect
            placeholder={cities.length ? undefined : 'Şehir'}
            data={sortTr(startups.map((s) => s.location))}
            value={cities}
            onChange={setCities}
            clearable
            searchable
            style={{ flex: '1 1 160px' }}
          />
          <MultiSelect
            placeholder={maturities.length ? undefined : 'Olgunluk'}
            data={MATURITY_ORDER.map((m) => ({ value: m, label: MATURITY_LABEL[m] }))}
            value={maturities}
            onChange={setMaturities}
            clearable
            style={{ flex: '1 1 160px' }}
          />
          <SegmentedControl
            value={view}
            onChange={setView}
            data={[
              { value: 'table', label: <IconList size={16} aria-label="Tablo" /> },
              { value: 'grid', label: <IconLayoutGrid size={16} aria-label="Kartlar" /> },
            ]}
          />
        </Group>
      </Card>

      <Text size="sm" c="dimmed" mb="sm">
        {rows.length} / {startups.length} girişim
      </Text>

      {view === 'table' ? (
        <div className="app-table-wrap">
          <Table.ScrollContainer minWidth={900}>
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th pl="lg">Girişim</Table.Th>
                  <Table.Th>Sektör</Table.Th>
                  <Table.Th>Olgunluk</Table.Th>
                  <Table.Th>Şehir</Table.Th>
                  <Table.Th pr="lg">Öne çıkan yetkinlikler</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {rows.map((s) => (
                  <Table.Tr key={s.id} className="app-row-link" onClick={() => open(s)}>
                    <Table.Td pl="lg" maw={360}>
                      <Group gap="sm" wrap="nowrap">
                        <OrgAvatar name={s.name} size={34} />
                        <div style={{ minWidth: 0 }}>
                          <Text size="sm" fw={600}>
                            {s.name}
                          </Text>
                          <Text size="xs" c="dimmed" lineClamp={1}>
                            {s.description}
                          </Text>
                        </div>
                      </Group>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{s.sector}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{MATURITY_LABEL[s.maturity]}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm" c={s.location === 'Belirtilmemiş' ? 'dimmed' : undefined} style={{ whiteSpace: 'nowrap' }}>
                        {s.location}
                      </Text>
                    </Table.Td>
                    <Table.Td pr="lg">
                      <Capabilities items={s.capabilities} />
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </div>
      ) : (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
          {rows.map((s) => (
            <Card key={s.id} padding="md" className="app-row-link" onClick={() => open(s)}>
              <Stack gap="sm">
                <Group gap="sm" wrap="nowrap">
                  <OrgAvatar name={s.name} size={40} />
                  <div style={{ minWidth: 0 }}>
                    <Text fw={600} truncate>
                      {s.name}
                    </Text>
                    <Group gap={6}>
                      <Text size="xs" c="dimmed">
                        {s.sector} · {MATURITY_LABEL[s.maturity]}
                      </Text>
                      <Group gap={2}>
                        <IconMapPin size={11} color="var(--app-muted)" />
                        <Text size="xs" c="dimmed">
                          {s.location}
                        </Text>
                      </Group>
                    </Group>
                  </div>
                </Group>
                <Text size="sm" c="dimmed" lineClamp={3} lh={1.5}>
                  {s.description}
                </Text>
                <Capabilities items={s.capabilities} max={2} />
              </Stack>
            </Card>
          ))}
        </SimpleGrid>
      )}

      <StartupDrawer startup={selected} onClose={() => setParams({})} />
    </>
  )
}
