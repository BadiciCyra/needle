import { Alert, Anchor, Box, Button, Card, Grid, Group, Stack, Stepper, Text, Textarea, Title } from '@mantine/core'
import { IconAlertCircle, IconRefresh, IconTargetArrow } from '@tabler/icons-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ApiError, api, toMatchView } from '../api'
import BriefCard from '../components/BriefCard'
import { StitchProgress } from '../components/StitchLoader'
import MatchResults from '../components/MatchResults'
import { OrgAvatar, PageLoader, StageBadge } from '../components/ui'
import { useAppData } from '../data'
import { stageOf, timeAgo } from '../labels'
import type { BriefOut, MatchView } from '../types'

export default function BriefPage() {
  const briefId = Number(useParams().briefId)
  const { needs, refresh } = useAppData()
  const need = needs?.find((n) => n.brief_id === briefId) ?? null
  const [brief, setBrief] = useState<BriefOut | null>(null)
  const [match, setMatch] = useState<MatchView | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<'answers' | 'match' | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const b = await api.getBrief(briefId)
      setBrief(b)
      if (b.status === 'final') {
        setMatch(await api.latestMatch(briefId).catch((e) => (e instanceof ApiError && e.status === 404 ? null : Promise.reject(e))))
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [briefId])

  useEffect(() => {
    load()
  }, [load])

  const submitAnswers = async () => {
    setBusy('answers')
    setError(null)
    try {
      setBrief(await api.answer(briefId, answers))
      refresh()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const runMatch = async () => {
    setBusy('match')
    setError(null)
    try {
      setMatch(toMatchView(await api.runMatch(briefId)))
      refresh()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  if (loading) return <PageLoader />
  if (!brief)
    return (
      <Alert color="red" variant="light" icon={<IconAlertCircle size={18} />} title="Brief yüklenemedi">
        {error}{' '}
        <Anchor component={Link} to="/ihtiyaclar">
          İhtiyaçlara dön
        </Anchor>
      </Alert>
    )

  const piloted = match?.shortlist.some((i) => i.status === 'accepted')
  const step = brief.status === 'needs_input' ? 1 : piloted ? 4 : match ? 3 : 2
  const pending = match?.shortlist.filter((i) => i.status === 'suggested').length ?? 0

  return (
    <>
      <Group justify="space-between" align="flex-end" mb="lg" wrap="wrap" gap="md">
        <div style={{ minWidth: 0 }}>
          <Group gap={6} mb={10}>
            <Anchor component={Link} to="/ihtiyaclar" size="sm" c="dimmed">
              İhtiyaçlar
            </Anchor>
            <Text size="sm" c="dimmed">
              /
            </Text>
            <Text size="sm" c="dimmed" truncate maw={300}>
              {need?.organization ?? `#${briefId}`}
            </Text>
          </Group>
          <Group gap="md" wrap="nowrap" align="center">
            <OrgAvatar name={need?.organization ?? brief.brief.title} size={48} color="gray" />
            <div style={{ minWidth: 0 }}>
              <Title order={1} className="app-display">
                {brief.brief.title}
              </Title>
              <Group gap="xs" mt={6}>
                {need && <StageBadge stage={stageOf(need)} />}
                {need && (
                  <Text size="sm" c="dimmed">
                    {timeAgo(need.created_at)} oluşturuldu
                  </Text>
                )}
              </Group>
            </div>
          </Group>
        </div>
        {brief.status === 'final' && (
          <Button
            leftSection={match ? <IconRefresh size={16} /> : <IconTargetArrow size={16} />}
            loading={busy === 'match'}
            onClick={runMatch}
            variant={match ? 'default' : 'filled'}
          >
            {match ? 'Yeniden eşleştir' : 'Uygun girişimleri bul'}
          </Button>
        )}
      </Group>

      <Card mb="lg" py="md">
        <Stepper active={step} size="xs" allowNextStepsSelect={false} iconSize={28}>
          <Stepper.Step label="İhtiyaç" description="Serbest metin" />
          <Stepper.Step label="Brief" description={brief.status === 'needs_input' ? 'Bilgi bekleniyor' : 'Tamamlandı'} />
          <Stepper.Step label="Eşleştirme" description={match ? `${match.shortlist.length} aday` : 'Yapılmadı'} />
          <Stepper.Step label="Pilot" description={piloted ? 'Başladı' : pending ? `${pending} karar bekliyor` : '—'} />
        </Stepper>
      </Card>

      {error && (
        <Alert color="red" variant="light" icon={<IconAlertCircle size={18} />} title="İşlem tamamlanamadı" mb="lg" withCloseButton onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid gap="lg">
        <Grid.Col span={{ base: 12, md: 5, lg: 4 }}>
          <Box style={{ position: 'sticky', top: 84 }}>
            <BriefCard brief={brief.brief} rawText={need?.raw_text} />
          </Box>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 7, lg: 8 }}>
          {busy === 'answers' ? (
            <StitchProgress
              title="Brief tamamlanıyor"
              description="Cevaplarınız ihtiyaç metniyle birleştirilip brief yeniden yazılıyor."
            />
          ) : brief.status === 'needs_input' ? (
            <Card>
              <Stack gap="md">
                <Group gap="sm" wrap="nowrap">
                  <div>
                    <Text className="app-display" fz={26}>
                      Eşleştirmeden önce {brief.questions.length} kısa soru
                    </Text>
                    <Text size="sm" c="dimmed">
                      Birkaç saniyelik sorular. Hazır cevaplardan birine dokunabilir ya da kendiniz yazabilirsiniz.
                    </Text>
                  </div>
                </Group>
                {brief.questions.map((q, i) => (
                  <div key={q.field}>
                    <Textarea
                      label={
                        <Text span fw={500} size="md">
                          <Text span className="app-num" c="var(--app-muted)" size="sm" mr={8}>
                            {String(i + 1).padStart(2, '0')}
                          </Text>
                          {q.question}
                        </Text>
                      }
                      placeholder="Kendi cevabınızı yazın ya da aşağıdan seçin. Bilmiyorsanız boş bırakın."
                      autosize
                      minRows={2}
                      value={answers[q.field] ?? ''}
                      onChange={(e) => setAnswers({ ...answers, [q.field]: e.currentTarget.value })}
                    />
                    {!!q.examples?.length && (
                      <Group gap={6} mt={8}>
                        {q.examples.map((example) => {
                          const selected = answers[q.field] === example
                          return (
                            <Button
                              key={example}
                              size="compact-sm"
                              variant={selected ? 'filled' : 'default'}
                              fw={400}
                              onClick={() => setAnswers({ ...answers, [q.field]: selected ? '' : example })}
                            >
                              {example}
                            </Button>
                          )
                        })}
                      </Group>
                    )}
                  </div>
                ))}
                <Group justify="flex-end">
                  <Button onClick={submitAnswers}>
                    Brief’i tamamla
                  </Button>
                </Group>
              </Stack>
            </Card>
          ) : busy === 'match' ? (
            <StitchProgress
              title="Adaylar aranıyor"
              description="Girişim havuzunda anlamsal arama yapılıyor, adaylar yeniden sıralanıyor ve her biri için gerekçe yazılıyor. Bu işlem bir dakika kadar sürebilir."
            />
          ) : match ? (
            <MatchResults view={match} onChange={setMatch} />
          ) : (
            <Card py={48}>
              <Stack align="center" gap="xs" maw={440} mx="auto" ta="center">
                <Text className="app-display" fz={30}>
                  Brief hazır
                </Text>
                <Text size="sm" c="dimmed">
                  Girişim havuzunda anlamsal arama yapılır; en uygun adaylar ve “yakındı ama” diye elenenler gerekçeleriyle
                  listelenir.
                </Text>
                <Button mt="sm" leftSection={<IconTargetArrow size={16} />} onClick={runMatch}>
                  Uygun girişimleri bul
                </Button>
              </Stack>
            </Card>
          )}
        </Grid.Col>
      </Grid>
    </>
  )
}
