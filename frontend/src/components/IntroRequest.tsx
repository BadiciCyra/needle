import { Button, Modal, Select, Stack, Text, TextInput, Textarea } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useState } from 'react'

import { api } from '../api'
import { useAuth } from '../auth'
import { useAppData } from '../data'
import { trFilter } from '../labels'
import type { StartupProfile } from '../types'

const OWN = 'kendi'

export default function IntroRequest({ startup }: { startup: StartupProfile }) {
  const { isStartup, isAdmin } = useAuth()
  const { needs, introductions, refresh } = useAppData()
  const [open, setOpen] = useState(false)
  const [choice, setChoice] = useState<string | null>(null)
  const [title, setTitle] = useState('')
  const [problem, setProblem] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  if (isStartup || !needs) return null

  const taken = new Set((introductions ?? []).filter((i) => i.startup.id === startup.id && i.status !== 'ret').map((i) => i.brief_id))
  const options = [
    ...needs.map((n) => ({
      value: String(n.brief_id),
      label: isAdmin && n.organization ? `${n.title} · ${n.organization}` : n.title,
      disabled: taken.has(n.brief_id),
    })),
    ...(isAdmin ? [] : [{ value: OWN, label: 'Listede yok, sorunu kendim yazacağım', disabled: false }]),
  ]
  const pending = needs.filter((n) => taken.has(n.brief_id))
  const selected = choice ?? (needs.length === 0 && !isAdmin ? OWN : null)
  const own = selected === OWN
  const ready = own ? title.trim().length >= 3 && problem.trim().length >= 20 : selected !== null

  const reset = () => {
    setOpen(false)
    setChoice(null)
    setTitle('')
    setProblem('')
    setNote('')
  }

  const submit = async () => {
    if (!ready || !selected) return
    setBusy(true)
    try {
      const subject = own ? { title: title.trim(), problem: problem.trim() } : { brief_id: Number(selected) }
      await api.createIntroduction({ ...subject, startup_id: startup.id, note: note.trim() || null })
      await refresh()
      notifications.show({
        color: 'teal',
        title: 'Tanıştırma isteği gönderildi',
        message: `${startup.name} kabul edince pilot kartı açılır.${own ? ' Yazdığınız sorun İhtiyaçlar listesine de eklendi.' : ''}`,
      })
      reset()
    } catch (e) {
      notifications.show({ color: 'red', title: 'İstek gönderilemedi', message: (e as Error).message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Button fullWidth onClick={() => setOpen(true)}>
        Tanışma iste
      </Button>
      {pending.length > 0 && (
        <Text size="xs" c="dimmed" mt={-8}>
          Bu girişimle süren tanışma: {pending.map((n) => n.title).join(', ')}
        </Text>
      )}
      <Modal opened={open} onClose={reset} title={`${startup.name} ile tanışma`} size="md">
        <Stack>
          <Text size="sm" c="dimmed">
            Eşleştirmenin önerip önermediğinden bağımsız olarak bu girişime istek gönderebilirsiniz. Girişim kabul edince pilot açılır.
          </Text>
          <Select
            label="Hangi sorununuz için?"
            placeholder="İhtiyaç seçin"
            data={options}
            value={selected}
            onChange={setChoice}
            searchable
            filter={trFilter}
            nothingFoundMessage="İhtiyaç bulunamadı"
            comboboxProps={{ withinPortal: true }}
          />
          {own && (
            <>
              <TextInput
                label="Kısa başlık"
                placeholder="Örn. Depo stok sayımının otomatikleşmesi"
                maxLength={120}
                value={title}
                onChange={(e) => setTitle(e.currentTarget.value)}
              />
              <Textarea
                label="Sorun"
                description="Kendi cümlelerinizle: ne oluyor, neden sorun, neyi değiştirmek istiyorsunuz. Yazdığınız haliyle ihtiyaçlarınıza da eklenir."
                placeholder="Örn. Üç depomuzda stok sayımı ayda bir elle yapılıyor; sayım iki gün sürüyor ve kayıtlarla fark çıkıyor."
                autosize
                minRows={4}
                maxLength={4000}
                value={problem}
                onChange={(e) => setProblem(e.currentTarget.value)}
                error={problem.trim().length > 0 && problem.trim().length < 20 ? 'En az 20 karakter yazın' : undefined}
              />
            </>
          )}
          <Textarea
            label="Girişime not"
            description="İsteğe bağlı: neden onlarla görüşmek istediğiniz"
            autosize
            minRows={2}
            maxLength={2000}
            value={note}
            onChange={(e) => setNote(e.currentTarget.value)}
          />
          <Button onClick={submit} loading={busy} disabled={!ready}>
            İsteği gönder
          </Button>
        </Stack>
      </Modal>
    </>
  )
}
