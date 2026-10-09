import { Alert, Anchor, Box, Button, Grid, Group, Progress, Stack, Table, Text, Tooltip } from '@mantine/core'
import { IconAlertCircle, IconDownload } from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api'
import { PageHeader, PageLoader, SectionCard, StatStrip, Tag } from '../components/ui'
import { TAG_COLOR } from '../labels'
import type { Report } from '../types'

const pct = (value: number | null) => (value === null ? '—' : `%${Math.round(value * 100)}`)

export default function ReportPage() {
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.report().then(setReport).catch((e) => setError((e as Error).message))
  }, [])

  if (error)
    return (
      <Alert color="red" variant="light" icon={<IconAlertCircle size={18} />} title="Rapor yüklenemedi">
        {error}
      </Alert>
    )
  if (!report) return <PageLoader />

  const f = report.funnel
  const i = report.introductions
  const p = report.pilots
  const funnel = [
    { label: 'İhtiyaç girildi', value: f.needs },
    { label: 'Brief tamamlandı', value: f.briefed },
    { label: 'Eşleştirme yapıldı', value: f.matched },
    { label: 'Tanıştırma istendi', value: f.introduced },
    { label: 'Pilota dönüştü', value: f.piloted },
    { label: 'İşe yaradı (evet / kısmen)', value: f.worked },
  ]
  const topMissing = report.missing_capabilities[0]?.needs ?? 1

  return (
    <>
      <PageHeader
        eyebrow={`Rapor · ${new Date(report.generated_at).toLocaleString('tr-TR', { dateStyle: 'long', timeStyle: 'short' })}`}
        title="Program raporu"
        description="İhtiyaçların pilota ve sonuca dönüşme oranı, sektörler ve havuzun karşılayamadığı yetkinlikler. Excel çıktısı aynı veriyi sayfa sayfa içerir."
        actions={
          <Button component="a" href="/api/admin/report.xlsx" download leftSection={<IconDownload size={15} />}>
            Excel indir
          </Button>
        }
      />

      <StatStrip
        items={[
          { label: 'İhtiyaç', value: f.needs, hint: `${f.no_match} tanesinde havuzda doğrudan çözen yok` },
          {
            label: 'Tanıştırma kabulü',
            value: pct(i.acceptance_rate),
            hint: i.avg_response_days === null ? 'Henüz cevap yok' : `Ortalama ${i.avg_response_days} günde cevap`,
          },
          { label: 'Pilot', value: p.total, hint: `${p.active} aktif · ${p.done} tamamlandı`, tone: p.stale ? 'alert' : undefined },
          { label: 'İşe yaradı', value: p.result_evet + p.result_kismen, hint: `${p.result_evet} evet · ${p.result_kismen} kısmen · ${p.result_hayir} hayır` },
          { label: 'Açık çağrı', value: report.open_calls, hint: `${report.applications} başvuru` },
        ]}
      />

      <Grid gap="lg">
        <Grid.Col span={{ base: 12, md: 7 }}>
          <Stack gap="lg">
            <SectionCard
              title="Havuzda eksik yetkinlikler"
              description="Uygun girişim bulunamayan ihtiyaçların aradığı ve “yakındı ama” adaylarında eksik kalan yetkinlikler. Ekosisteme hangi girişimlerin çekilmesi gerektiğini gösterir."
              padding="0"
            >
              {report.missing_capabilities.length === 0 ? (
                <Text size="sm" c="var(--app-muted)" p="lg">
                  Henüz veri yok. Eşleştirme yapıldıkça dolar.
                </Text>
              ) : (
                <Table>
                  <Table.Tbody>
                    {report.missing_capabilities.map((m) => (
                      <Table.Tr key={m.capability}>
                        <Table.Td pl="lg">
                          <Tooltip
                            multiline
                            w={320}
                            label={
                              <>
                                {m.need_titles.join(' · ')}
                                {m.variants.length > 0 && <Box mt={4}>Diğer yazımlar: {m.variants.join(', ')}</Box>}
                              </>
                            }
                          >
                            <Text size="sm" fw={500}>
                              {m.capability}
                            </Text>
                          </Tooltip>
                        </Table.Td>
                        <Table.Td w={180}>
                          <Progress value={(m.needs / topMissing) * 100} color="thread.6" />
                        </Table.Td>
                        <Table.Td pr="lg" w={110} ta="right">
                          <Text size="xs" className="app-num" c="var(--app-muted)" style={{ whiteSpace: 'nowrap' }}>
                            {m.needs} ihtiyaç
                          </Text>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              )}
            </SectionCard>

            <SectionCard
              title="Uygun girişim bulunamayan ihtiyaçlar"
              description="Son eşleştirmede problemi doğrudan çözen girişim çıkmadı. Açık çağrıya çevrilmeyenler bekliyor."
              padding="0"
            >
              {report.unmet_needs.length === 0 ? (
                <Text size="sm" c="var(--app-muted)" p="lg">
                  Bütün eşleştirilen ihtiyaçlarda en az bir doğrudan çözen aday bulundu.
                </Text>
              ) : (
                <Table>
                  <Table.Tbody>
                    {report.unmet_needs.map((u) => (
                      <Table.Tr key={u.brief_id}>
                        <Table.Td pl="lg">
                          <Anchor component={Link} to={`/ihtiyaclar/${u.brief_id}`} size="sm" c="var(--app-ink)" fw={500}>
                            {u.title}
                          </Anchor>
                          <Text size="xs" c="var(--app-muted)">
                            {u.organization ?? 'Kurum belirtilmedi'} · {u.required_capabilities.join(', ')}
                          </Text>
                        </Table.Td>
                        <Table.Td pr="lg" ta="right" w={190}>
                          {u.open_call_id ? (
                            <Anchor component={Link} to={`/cagrilar/${u.open_call_id}`} size="xs">
                              Çağrıda · {u.applications} başvuru
                            </Anchor>
                          ) : (
                            <Tag color={TAG_COLOR.ochre}>Çağrı açılmadı</Tag>
                          )}
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              )}
            </SectionCard>

            <SectionCard title="Sektörler" description="Talep tarafı: kurumların sektörüne göre" padding="0">
              <Table.ScrollContainer minWidth={520}>
                <Table>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th pl="lg">Sektör</Table.Th>
                      <Table.Th ta="right">İhtiyaç</Table.Th>
                      <Table.Th ta="right">Uygun yok</Table.Th>
                      <Table.Th ta="right">Tanıştırılan</Table.Th>
                      <Table.Th ta="right">Pilot</Table.Th>
                      <Table.Th pr="lg" ta="right">
                        İşe yaradı
                      </Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {report.sectors.map((s) => (
                      <Table.Tr key={s.sector}>
                        <Table.Td pl="lg">{s.sector}</Table.Td>
                        {[s.needs, s.no_match, s.introduced, s.pilots].map((v, idx) => (
                          <Table.Td key={idx} ta="right" className="app-num">
                            {v}
                          </Table.Td>
                        ))}
                        <Table.Td pr="lg" ta="right" className="app-num">
                          {s.worked}
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            </SectionCard>
          </Stack>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 5 }}>
          <Stack gap="lg">
            <SectionCard title="Akış" description="Her adıma ulaşan ihtiyaç sayısı">
              <Stack gap={14}>
                {funnel.map((step, idx) => {
                  const share = f.needs ? (step.value / f.needs) * 100 : 0
                  return (
                    <div key={step.label}>
                      <Group justify="space-between" mb={6} wrap="nowrap">
                        <Text size="sm">
                          <Text span className="app-num" c="var(--app-muted)" size="xs" mr={10}>
                            {String(idx + 1).padStart(2, '0')}
                          </Text>
                          {step.label}
                        </Text>
                        <Text size="sm" className="app-num">
                          {step.value}
                          <Text span c="var(--app-muted)" size="xs" ml={8}>
                            {Math.round(share)}%
                          </Text>
                        </Text>
                      </Group>
                      <Progress value={share} color={idx === funnel.length - 1 ? 'thread.6' : 'ink'} />
                    </div>
                  )
                })}
              </Stack>
            </SectionCard>

            <SectionCard title="Tanıştırmalar">
              <Stack gap={6}>
                <Text size="sm">
                  {i.total} istek · {i.waiting} bekliyor · {i.accepted} kabul · {i.declined} ret
                </Text>
                <Text size="xs" c="var(--app-muted)">
                  {i.via_admin} tanesi hesabı olmayan girişim adına program yöneticisi tarafından cevaplandı. Kabul oranı ve
                  cevap süresi yalnızca eşleştirmeden gelen isteklerle hesaplanır (çağrı başvuruları zaten ilgi bildirir).
                </Text>
              </Stack>
            </SectionCard>

            <SectionCard title="Girişim havuzu" description="Arz tarafı: sektöre göre girişim ve hesabı olanlar" padding="0">
              <Table>
                <Table.Tbody>
                  {report.pool.slice(0, 12).map((r) => (
                    <Table.Tr key={r.sector}>
                      <Table.Td pl="lg">
                        <Text size="sm">{r.sector}</Text>
                      </Table.Td>
                      <Table.Td pr="lg" ta="right">
                        <Text size="xs" className="app-num" c="var(--app-muted)">
                          {r.startups} girişim{r.with_account ? ` · ${r.with_account} hesaplı` : ''}
                        </Text>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </SectionCard>
          </Stack>
        </Grid.Col>
      </Grid>
    </>
  )
}
