import { Button, Checkbox, Group, Modal, Stack, Text, Textarea, TextInput } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api'
import { useAppData } from '../data'
import type { Brief } from '../types'

function draftSummary(brief: Brief): string {
  return [
    brief.problem,
    brief.scope && `Kapsam: ${brief.scope}`,
    brief.required_capabilities.length > 0 && `Aranan yetkinlikler: ${brief.required_capabilities.join(', ')}`,
    brief.success_criteria && `Başarı kriteri: ${brief.success_criteria}`,
    brief.timeline && `Süre: ${brief.timeline}`,
  ]
    .filter(Boolean)
    .join('\n\n')
}

export default function OpenCallModal({
  briefId,
  brief,
  opened,
  onClose,
}: {
  briefId: number
  brief: Brief
  opened: boolean
  onClose: () => void
}) {
  const navigate = useNavigate()
  const { refresh } = useAppData()
  const [title, setTitle] = useState(brief.title)
  const [summary, setSummary] = useState(() => draftSummary(brief))
  const [hide, setHide] = useState(false)
  const [deadline, setDeadline] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setBusy(true)
    try {
      const call = await api.createCall({
        brief_id: briefId,
        title: title.trim(),
        summary: summary.trim(),
        hide_organization: hide,
        deadline: deadline || null,
      })
      await refresh()
      notifications.show({ color: 'teal', title: 'Çağrı yayında', message: 'Girişimler başvurdukça burada göreceksiniz.' })
      navigate(`/cagrilar/${call.id}`)
    } catch (e) {
      notifications.show({ color: 'red', title: 'Çağrı açılamadı', message: (e as Error).message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal opened={opened} onClose={onClose} size="lg" title={<Text fw={600}>Açık çağrı aç</Text>}>
      <Stack>
        <Text size="sm" c="dimmed">
          Havuzda bu ihtiyacı doğrudan çözen girişim bulunamadığında ihtiyacı girişimlere duyurun. Doğrulanmış girişimler
          başvurur; uygun bulduğunuz başvuru için pilot doğrudan açılır.
        </Text>
        <TextInput label="Başlık" required value={title} onChange={(e) => setTitle(e.currentTarget.value)} />
        <Textarea
          label="Girişimlerin göreceği metin"
          description="Brief’ten hazırlandı. Gizli kalması gereken bilgileri çıkarın."
          autosize
          minRows={6}
          value={summary}
          onChange={(e) => setSummary(e.currentTarget.value)}
        />
        <Group align="flex-end">
          <TextInput label="Son başvuru tarihi" description="İsteğe bağlı" type="date" value={deadline} onChange={(e) => setDeadline(e.currentTarget.value)} w={200} />
          <Checkbox label="Kurum adını girişimlere gösterme" checked={hide} onChange={(e) => setHide(e.currentTarget.checked)} mb={8} />
        </Group>
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            Vazgeç
          </Button>
          <Button loading={busy} disabled={title.trim().length < 5 || summary.trim().length < 20} onClick={submit}>
            Çağrıyı yayınla
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
