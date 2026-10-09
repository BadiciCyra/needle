import { Alert, Button, Modal, Select, Stack, Text, Textarea } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconInfoCircle } from '@tabler/icons-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api'
import { useAuth } from '../auth'
import { useAppData } from '../data'
import { trFilter } from '../labels'
import type { StartupProfile } from '../types'

export default function IntroRequest({ startup }: { startup: StartupProfile }) {
  const { isStartup, isAdmin } = useAuth()
  const { needs, introductions, refresh } = useAppData()
  const [open, setOpen] = useState(false)
  const [briefId, setBriefId] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  if (isStartup || !needs) return null

  const taken = new Set((introductions ?? []).filter((i) => i.startup.id === startup.id && i.status !== 'ret').map((i) => i.brief_id))
  const options = needs.map((n) => ({
    value: String(n.brief_id),
    label: isAdmin && n.organization ? `${n.title} · ${n.organization}` : n.title,
    disabled: taken.has(n.brief_id),
  }))
  const pending = needs.filter((n) => taken.has(n.brief_id))

  const submit = async () => {
    if (!briefId) return
    setBusy(true)
    try {
      await api.createIntroduction({ brief_id: Number(briefId), startup_id: startup.id, note: note.trim() || null })
      await refresh()
      notifications.show({
        color: 'teal',
        title: 'Tanıştırma isteği gönderildi',
        message: `${startup.name} kabul edince pilot kartı açılır. Tanıştırmalar sayfasından takip edebilirsiniz.`,
      })
      setOpen(false)
      setBriefId(null)
      setNote('')
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
      <Modal opened={open} onClose={() => setOpen(false)} title={`${startup.name} ile tanışma`} size="md">
        {needs.length === 0 ? (
          <Alert variant="light" color="gray" icon={<IconInfoCircle size={18} />}>
            <Stack gap="xs" align="flex-start">
              <Text size="sm">Tanışma bir ihtiyaç üzerinden açılır; pilot planı o ihtiyacın brief'inden hazırlanır. Önce ihtiyacınızı girin.</Text>
              <Button size="xs" component={Link} to="/ihtiyaclar/yeni">
                Yeni ihtiyaç
              </Button>
            </Stack>
          </Alert>
        ) : (
          <Stack>
            <Text size="sm" c="dimmed">
              Eşleştirmenin önerip önermediğinden bağımsız olarak bu girişime istek gönderebilirsiniz. Girişim kabul edince pilot açılır.
            </Text>
            <Select
              label="Hangi ihtiyacınız için?"
              placeholder="İhtiyaç seçin"
              data={options}
              value={briefId}
              onChange={setBriefId}
              searchable
              filter={trFilter}
              nothingFoundMessage="İhtiyaç bulunamadı"
              comboboxProps={{ withinPortal: true }}
            />
            <Textarea
              label="Girişime not"
              description="İsteğe bağlı: neden onlarla görüşmek istediğiniz"
              autosize
              minRows={3}
              maxLength={2000}
              value={note}
              onChange={(e) => setNote(e.currentTarget.value)}
            />
            <Button onClick={submit} loading={busy} disabled={!briefId}>
              İsteği gönder
            </Button>
          </Stack>
        )}
      </Modal>
    </>
  )
}
