import { Alert, Box, Button, Card, Checkbox, Chip, Group, Stack, Stepper, Text, Textarea, TextInput, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconAlertCircle, IconArrowLeft, IconArrowRight, IconCheck } from '@tabler/icons-react'
import { useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../auth'
import { BUDGET_RANGES, CITIES, DATA_CONSTRAINTS, EMPLOYEE_RANGES, PILOT_DURATIONS, SECTORS, SYSTEMS } from '../catalog'
import { PageHeader } from '../components/ui'
import { MATURITY_LABEL, MATURITY_ORDER } from '../labels'
import type { OrgProfile } from '../types'

function Question({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <div role="group" aria-label={title}>
      <Text fw={500}>{title}</Text>
      {hint && (
        <Text size="sm" c="dimmed" mb={8}>
          {hint}
        </Text>
      )}
      <Box mt={hint ? 0 : 8}>{children}</Box>
    </div>
  )
}

function Choice<T extends string>({ value, options, onChange }: { value: T | null; options: readonly { value: T; label: string }[]; onChange: (v: T) => void }) {
  return (
    <Chip.Group value={value as string | null} onChange={(v: string) => onChange(v as T)}>
      <Group gap={6}>
        {options.map((o) => (
          <Chip key={o.value} value={o.value} radius="xs" variant="outline">
            {o.label}
          </Chip>
        ))}
      </Group>
    </Chip.Group>
  )
}

function Multi({ value, options, onChange }: { value: string[]; options: string[]; onChange: (v: string[]) => void }) {
  return (
    <Chip.Group multiple value={value} onChange={onChange}>
      <Group gap={6}>
        {options.map((o) => (
          <Chip key={o} value={o} radius="xs" variant="outline">
            {o}
          </Chip>
        ))}
      </Group>
    </Chip.Group>
  )
}

const asOptions = (values: string[]) => values.map((v) => ({ value: v, label: v }))

export default function OnboardingPage({ mode = 'onboarding' }: { mode?: 'onboarding' | 'edit' }) {
  const { me, saveProfile } = useAuth()
  const navigate = useNavigate()
  const existing = me?.organization?.profile ?? {}
  const [profile, setProfile] = useState<Partial<OrgProfile>>({
    systems: [],
    data_constraints: [],
    startup_location: 'fark_etmez',
    directory_visible: true,
    ...existing,
  })
  const [step, setStep] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = <K extends keyof OrgProfile>(key: K, value: OrgProfile[K]) => setProfile((p) => ({ ...p, [key]: value }))

  const websiteOk = !profile.website?.trim() || /^https?:\/\//.test(profile.website.trim())
  const step1Done = !!profile.sector && !!profile.city && !!profile.employee_range && websiteOk

  const finish = async () => {
    setBusy(true)
    setError(null)
    if (mode === 'onboarding') navigate('/ihtiyaclar/yeni', { replace: true })
    try {
      await saveProfile({
        sector: profile.sector!,
        city: profile.city!,
        employee_range: profile.employee_range!,
        systems: profile.systems ?? [],
        preferred_maturity: profile.preferred_maturity ?? null,
        startup_location: profile.startup_location ?? 'fark_etmez',
        budget_range: profile.budget_range ?? null,
        pilot_duration: profile.pilot_duration ?? null,
        data_constraints: profile.data_constraints ?? [],
        description: profile.description?.trim() || null,
        website: profile.website?.trim() || null,
        directory_visible: profile.directory_visible ?? true,
      })
      if (mode === 'edit') {
        notifications.show({ message: 'Firma profili kaydedildi' })
        navigate('/')
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const steps = [
    {
      label: 'Firmanız',
      content: (
        <Stack gap="xl">
          <Question title="Hangi sektördesiniz?">
            <Choice value={profile.sector ?? null} options={asOptions(SECTORS)} onChange={(v) => set('sector', v)} />
          </Question>
          <Question title="Merkeziniz hangi şehirde?">
            <Choice value={profile.city ?? null} options={asOptions(CITIES)} onChange={(v) => set('city', v)} />
          </Question>
          <Question title="Kaç kişi çalışıyor?">
            <Choice value={profile.employee_range ?? null} options={EMPLOYEE_RANGES} onChange={(v) => set('employee_range', v)} />
          </Question>
          <Question title="Firmanız ne iş yapıyor?" hint="İsteğe bağlı. Girişimler Kurumlar sayfasında sizi bu tanıtımla görür; iki üç cümle yeter.">
            <Textarea
              placeholder="Örn. Beyaz eşya üretiyor, Türkiye genelinde 1.200 bayi ile satıyoruz."
              autosize
              minRows={2}
              maxLength={600}
              value={profile.description ?? ''}
              onChange={(e) => set('description', e.currentTarget.value)}
            />
          </Question>
          <Question title="Web siteniz">
            <TextInput
              placeholder="https://"
              value={profile.website ?? ''}
              onChange={(e) => set('website', e.currentTarget.value)}
              error={websiteOk ? undefined : 'https:// ile başlamalı'}
            />
          </Question>
          <Checkbox
            checked={profile.directory_visible ?? true}
            onChange={(e) => set('directory_visible', e.currentTarget.checked)}
            label="Firmamı girişimlere Kurumlar sayfasında göster"
            description="Yalnızca ad, sektör, şehir, büyüklük, tanıtım ve kurum adını gizlemeyen açık çağrılar görünür. İhtiyaçlarınız ve buradaki diğer ayarlar gizli kalır."
          />
        </Stack>
      ),
    },
    {
      label: 'Çalışma şekliniz',
      content: (
        <Stack gap="xl">
          <Question title="Hangi sistemleri kullanıyorsunuz?" hint="Girişimin çözümü bunlarla konuşabilmeli. Birden fazla seçebilirsiniz.">
            <Multi value={profile.systems ?? []} options={SYSTEMS} onChange={(v) => set('systems', v)} />
          </Question>
          <Question title="Verinizle ilgili bir sınır var mı?" hint="Örneğin verinin şirket dışına çıkamaması, uygun girişimleri daraltır.">
            <Multi value={profile.data_constraints ?? []} options={DATA_CONSTRAINTS} onChange={(v) => set('data_constraints', v)} />
          </Question>
        </Stack>
      ),
    },
    {
      label: 'Girişim tercihiniz',
      content: (
        <Stack gap="xl">
          <Question title="Nasıl bir girişimle çalışmak istersiniz?" hint="En az hangi aşamada olsun?">
            <Choice
              value={profile.preferred_maturity ?? null}
              options={MATURITY_ORDER.map((m) => ({ value: m, label: MATURITY_LABEL[m] }))}
              onChange={(v) => set('preferred_maturity', v)}
            />
          </Question>
          <Question title="Girişim sizinle aynı şehirde mi olsun?">
            <Choice
              value={profile.startup_location ?? null}
              options={[
                { value: 'ayni_sehir', label: 'Evet, aynı şehirde' },
                { value: 'fark_etmez', label: 'Fark etmez' },
              ]}
              onChange={(v) => set('startup_location', v)}
            />
          </Question>
          <Question title="Bir deneme için ayırabileceğiniz bütçe?">
            <Choice value={profile.budget_range ?? null} options={asOptions(BUDGET_RANGES)} onChange={(v) => set('budget_range', v)} />
          </Question>
          <Question title="Bir denemenin sonucunu ne kadar sürede görmek istersiniz?">
            <Choice value={profile.pilot_duration ?? null} options={asOptions(PILOT_DURATIONS)} onChange={(v) => set('pilot_duration', v)} />
          </Question>
        </Stack>
      ),
    },
  ]

  return (
    <Box maw={760} mx="auto" py={mode === 'onboarding' ? 48 : 0} px={mode === 'onboarding' ? 'md' : 0}>
      {mode === 'onboarding' ? (
        <Box mb={32}>
          <div className="app-eyebrow" style={{ marginBottom: 10 }}>
            {me?.organization?.name}
          </div>
          <Title order={1} className="app-display">
            Sizi biraz tanıyalım
          </Title>
          <Text c="dimmed" mt={8} maw={560}>
            Üç kısa adım. Bu bilgiler her ihtiyaçta tekrar sorulmaz; eşleştirmeyi firmanıza göre daraltmak için kullanılır.
            Sonradan değiştirebilirsiniz.
          </Text>
        </Box>
      ) : (
        <PageHeader title="Firma profili" description="Eşleştirmede boş kalan bilgiler buradan tamamlanır." />
      )}

      <Card>
        <Stepper active={step} onStepClick={(i) => (i === 0 || step1Done) && setStep(i)} size="xs" mb="xl">
          {steps.map((s) => (
            <Stepper.Step key={s.label} label={s.label} />
          ))}
        </Stepper>

        {steps[step]!.content}

        {error && (
          <Alert color="red" variant="light" icon={<IconAlertCircle size={18} />} mt="xl">
            {error}
          </Alert>
        )}

        <Group justify="space-between" mt={36}>
          <Button variant="default" leftSection={<IconArrowLeft size={15} />} disabled={step === 0} onClick={() => setStep(step - 1)}>
            Geri
          </Button>
          {step < steps.length - 1 ? (
            <Button rightSection={<IconArrowRight size={15} />} disabled={step === 0 && !step1Done} onClick={() => setStep(step + 1)}>
              Devam
            </Button>
          ) : (
            <Button leftSection={<IconCheck size={15} />} loading={busy} disabled={!step1Done} onClick={finish}>
              {mode === 'edit' ? 'Kaydet' : 'Bitir ve ilk ihtiyacı yaz'}
            </Button>
          )}
        </Group>
      </Card>
    </Box>
  )
}
