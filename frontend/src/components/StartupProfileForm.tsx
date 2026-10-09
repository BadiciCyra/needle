import { Button, Group, Select, SimpleGrid, Stack, TagsInput, Textarea, TextInput } from '@mantine/core'
import { useState, type FormEvent } from 'react'

import { CITIES, STARTUP_SECTORS } from '../catalog'
import { MATURITY_LABEL, MATURITY_ORDER, trFilter } from '../labels'
import type { Maturity, StartupProfile, StartupProfileInput } from '../types'

const EMPTY: StartupProfileInput = {
  name: '',
  sector: '',
  maturity: 'mvp',
  location: '',
  website: '',
  description: '',
  capabilities: [],
  past_pilots: [],
}

export function toInput(p: StartupProfile): StartupProfileInput {
  return {
    name: p.name,
    sector: p.sector,
    maturity: p.maturity,
    location: p.location,
    website: p.website ?? '',
    description: p.description,
    capabilities: p.capabilities,
    past_pilots: p.past_pilots,
  }
}

export default function StartupProfileForm({
  initial,
  submitLabel,
  onSubmit,
}: {
  initial?: StartupProfileInput
  submitLabel: string
  onSubmit: (profile: StartupProfileInput) => Promise<void>
}) {
  const [form, setForm] = useState<StartupProfileInput>(initial ?? EMPTY)
  const [busy, setBusy] = useState(false)
  const set = <K extends keyof StartupProfileInput>(key: K, value: StartupProfileInput[K]) => setForm({ ...form, [key]: value })
  const cities = CITIES.includes(form.location) || !form.location ? CITIES : [form.location, ...CITIES]

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      await onSubmit({ ...form, website: form.website?.trim() || null })
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit}>
      <Stack>
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <TextInput label="Girişim adı" required value={form.name} onChange={(e) => set('name', e.currentTarget.value)} />
          <TextInput
            label="Web sitesi"
            placeholder="https://"
            value={form.website ?? ''}
            onChange={(e) => set('website', e.currentTarget.value)}
            error={form.website && !/^https?:\/\//.test(form.website) ? 'https:// ile başlamalı' : undefined}
          />
          <Select label="Sektör" required searchable filter={trFilter} data={STARTUP_SECTORS} value={form.sector || null} onChange={(v) => set('sector', v ?? '')} />
          <Select label="Şehir" required searchable filter={trFilter} data={cities} value={form.location || null} onChange={(v) => set('location', v ?? '')} />
          <Select
            label="Olgunluk"
            required
            allowDeselect={false}
            data={MATURITY_ORDER.map((m) => ({ value: m, label: MATURITY_LABEL[m] }))}
            value={form.maturity}
            onChange={(v) => v && set('maturity', v as Maturity)}
          />
        </SimpleGrid>
        <Textarea
          label="Ne yapıyorsunuz?"
          description="Kurumlara hangi problemi nasıl çözdüğünüzü 2-3 cümleyle yazın. Eşleştirme bu metinle yapılır."
          required
          autosize
          minRows={3}
          minLength={20}
          value={form.description}
          onChange={(e) => set('description', e.currentTarget.value)}
        />
        <TagsInput
          label="Yetkinlikler"
          description="Somut yazın: “yapay zeka” değil “görüntü işleme ile kumaş hata tespiti”. Her birinden sonra Enter."
          required
          maxTags={10}
          value={form.capabilities}
          onChange={(v) => set('capabilities', v)}
        />
        <TagsInput
          label="Referanslar / geçmiş pilotlar"
          description="İsteğe bağlı. Çalıştığınız kurumlar veya tamamlanan pilotlar."
          maxTags={10}
          value={form.past_pilots}
          onChange={(v) => set('past_pilots', v)}
        />
        <Group justify="flex-end">
          <Button
            type="submit"
            loading={busy}
            disabled={!form.name || !form.sector || !form.location || form.description.length < 20 || form.capabilities.length < 2}
          >
            {submitLabel}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
