import { Button, Group, Modal, PasswordInput, Stack, Text } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useState, type FormEvent } from 'react'

import { api } from '../api'

export default function PasswordModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [again, setAgain] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const close = () => {
    setCurrent('')
    setNext('')
    setAgain('')
    setError(null)
    onClose()
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (next !== again) return setError('Yeni şifreler aynı değil')
    setBusy(true)
    setError(null)
    try {
      await api.changePassword(current, next)
      notifications.show({ color: 'teal', message: 'Şifreniz değişti. Diğer cihazlardaki oturumlar kapatıldı.' })
      close()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal opened={opened} onClose={close} title={<Text fw={600}>Şifre değiştir</Text>}>
      <form onSubmit={submit}>
        <Stack>
          <PasswordInput label="Mevcut şifre" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.currentTarget.value)} />
          <PasswordInput label="Yeni şifre" description="En az 10 karakter" autoComplete="new-password" required minLength={10} value={next} onChange={(e) => setNext(e.currentTarget.value)} />
          <PasswordInput label="Yeni şifre (tekrar)" autoComplete="new-password" required value={again} onChange={(e) => setAgain(e.currentTarget.value)} error={error} />
          <Text size="xs" c="dimmed">
            Kaydettiğinizde diğer cihazlardaki oturumlarınız kapanır.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={close}>
              Vazgeç
            </Button>
            <Button type="submit" loading={busy} disabled={!current || next.length < 10}>
              Kaydet
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  )
}
