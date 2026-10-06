import { Button, Group, ScrollArea, SegmentedControl, Table, Text, TextInput } from '@mantine/core'
import { IconFileDescription, IconPlus, IconSearch } from '@tabler/icons-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { EmptyState, OrgAvatar, PageHeader, PageLoader, StageBadge } from '../components/ui'
import { useAppData } from '../data'
import { formatDate, STAGE, stageOf, type Stage } from '../labels'

const norm = (s: string) => s.toLocaleLowerCase('tr-TR')

export default function NeedsPage() {
  const navigate = useNavigate()
  const { needs } = useAppData()
  const [params, setParams] = useSearchParams()
  const stage = (params.get('asama') as Stage | null) ?? 'all'
  const [query, setQuery] = useState('')

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: needs?.length ?? 0 }
    needs?.forEach((n) => (c[stageOf(n)] = (c[stageOf(n)] ?? 0) + 1))
    return c
  }, [needs])

  const rows = useMemo(() => {
    const q = norm(query.trim())
    return (needs ?? []).filter(
      (n) =>
        (stage === 'all' || stageOf(n) === stage) &&
        (!q || norm(`${n.title} ${n.organization ?? ''} ${n.raw_text}`).includes(q)),
    )
  }, [needs, stage, query])

  if (!needs) return <PageLoader />

  return (
    <>
      <PageHeader
        title="İhtiyaçlar"
        description="Kurumların ihtiyaçları ve süreçteki aşamaları."
        actions={
          <Button component={Link} to="/ihtiyaclar/yeni" leftSection={<IconPlus size={16} />}>
            Yeni ihtiyaç
          </Button>
        }
      />

      {needs.length === 0 ? (
        <EmptyState
          icon={IconFileDescription}
          title="Henüz ihtiyaç yok"
          description="İlk ihtiyacı girdiğinizde burada aşamasıyla birlikte listelenir."
          action={
            <Button component={Link} to="/ihtiyaclar/yeni" leftSection={<IconPlus size={16} />}>
              Yeni ihtiyaç
            </Button>
          }
        />
      ) : (
        <>
          <Group justify="space-between" mb="md" wrap="wrap" gap="sm">
            <ScrollArea type="never">
              <SegmentedControl
                value={stage}
                onChange={(v) => setParams(v === 'all' ? {} : { asama: v })}
                data={[
                  { value: 'all', label: `Tümü · ${counts.all}` },
                  ...(Object.keys(STAGE) as Stage[]).map((s) => ({ value: s, label: `${STAGE[s].label} · ${counts[s] ?? 0}` })),
                ]}
              />
            </ScrollArea>
            <TextInput
              leftSection={<IconSearch size={16} />}
              placeholder="İhtiyaç veya kurum ara"
              value={query}
              onChange={(e) => setQuery(e.currentTarget.value)}
              w={{ base: '100%', sm: 280 }}
            />
          </Group>

          <div className="app-table-wrap">
            <Table.ScrollContainer minWidth={760}>
              <Table>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th pl="lg">İhtiyaç</Table.Th>
                    <Table.Th>Aşama</Table.Th>
                    <Table.Th ta="right">Aday</Table.Th>
                    <Table.Th ta="right">Pilot</Table.Th>
                    <Table.Th pr="lg" ta="right">
                      Oluşturuldu
                    </Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {rows.map((n) => (
                    <Table.Tr key={n.brief_id} className="app-row-link" onClick={() => navigate(`/ihtiyaclar/${n.brief_id}`)}>
                      <Table.Td pl="lg" maw={520}>
                        <Group gap="sm" wrap="nowrap">
                          <OrgAvatar name={n.organization ?? n.title} size={36} color="gray" />
                          <div style={{ minWidth: 0 }}>
                            <Text size="sm" fw={600} lineClamp={1}>
                              {n.title}
                            </Text>
                            <Text size="xs" c="dimmed" lineClamp={1}>
                              {n.organization ? `${n.organization} · ` : ''}
                              {n.raw_text}
                            </Text>
                          </div>
                        </Group>
                      </Table.Td>
                      <Table.Td>
                        <StageBadge stage={stageOf(n)} />
                      </Table.Td>
                      <Table.Td ta="right">
                        <Text size="sm" style={{ fontVariantNumeric: 'tabular-nums' }}>
                          {n.shortlist_count || '—'}
                        </Text>
                      </Table.Td>
                      <Table.Td ta="right">
                        {n.accepted_count ? (
                          <Text size="sm" className="app-num">
                            {n.accepted_count}
                          </Text>
                        ) : (
                          <Text size="sm" c="dimmed">
                            —
                          </Text>
                        )}
                      </Table.Td>
                      <Table.Td pr="lg" ta="right">
                        <Text size="sm" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
                          {formatDate(n.created_at)}
                        </Text>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                  {rows.length === 0 && (
                    <Table.Tr>
                      <Table.Td colSpan={5} py="xl" ta="center">
                        <Text size="sm" c="dimmed">
                          Bu filtreye uyan ihtiyaç yok.
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
