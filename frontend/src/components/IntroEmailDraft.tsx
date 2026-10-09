import { Alert, Anchor, Button, Collapse, CopyButton, Group, Stack, Text, Textarea, TextInput } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconCheck, IconCopy, IconMail, IconMailForward } from '@tabler/icons-react'
import { useState } from 'react'

import { api } from '../api'
import { formatDate, TAG_COLOR } from '../labels'
import type { Introduction } from '../types'
import { Tag } from './ui'

export default function IntroEmailDraft({ intro, onChange }: { intro: Introduction; onChange: (i: Introduction) => void }) {
  const email = intro.email
  const [open, setOpen] = useState(!email?.sent_at)
  const [to, setTo] = useState(email?.to ?? '')
  const [subject, setSubject] = useState(email?.subject ?? '')
  const [body, setBody] = useState(email?.body ?? '')
  const [busy, setBusy] = useState(false)

  const run = async (action: () => Promise<Introduction>, message?: string) => {
    setBusy(true)
    try {
      const updated = await action()
      onChange(updated)
      if (updated.email) {
        setTo(updated.email.to ?? '')
        setSubject(updated.email.subject)
        setBody(updated.email.body)
      }
      if (message) notifications.show({ color: 'teal', message })
    } catch (e) {
      notifications.show({ color: 'red', title: 'Kaydedilemedi', message: (e as Error).message })
    } finally {
      setBusy(false)
    }
  }

  if (!email)
    return (
      <Group justify="space-between" className="app-evidence">
        <Text size="sm" c="dimmed">
          Girişimin Needle hesabı yok; isteği e-postayla iletebilirsiniz.
        </Text>
        <Button size="xs" variant="default" leftSection={<IconMail size={14} />} loading={busy} onClick={() => run(() => api.createIntroEmail(intro.id))}>
          E-posta taslağı hazırla
        </Button>
      </Group>
    )

  const sent = !!email.sent_at
  const dirty = to !== (email.to ?? '') || subject !== email.subject || body !== email.body
  const mailto = `mailto:${encodeURIComponent(to)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`

  return (
    <div className="app-evidence">
      <Group justify="space-between" wrap="nowrap">
        <Group gap="xs">
          <Text size="sm" fw={600}>
            E-posta taslağı
          </Text>
          {sent ? (
            <Tag color={TAG_COLOR.green}>Gönderildi · {formatDate(email.sent_at)}</Tag>
          ) : (
            <Tag color={TAG_COLOR.ochre}>Gönderilmedi</Tag>
          )}
        </Group>
        <Anchor component="button" size="xs" c="dimmed" onClick={() => setOpen((o) => !o)}>
          {open ? 'Gizle' : 'Göster'}
        </Anchor>
      </Group>
      <Collapse expanded={open}>
        <Stack gap="xs" mt="sm">
          {!email.to && (
            <Alert color="yellow" variant="light" p="xs">
              <Text size="xs">
                Girişimin sitesinde e-posta adresi bulunamadı.
                {intro.startup.website && (
                  <>
                    {' '}
                    <Anchor href={intro.startup.website} target="_blank" rel="noreferrer" size="xs">
                      Sitesine bakın
                    </Anchor>{' '}
                    ve adresi aşağıya yazın.
                  </>
                )}
              </Text>
            </Alert>
          )}
          <TextInput
            label="Kime"
            size="xs"
            disabled={sent}
            value={to}
            onChange={(e) => setTo(e.currentTarget.value)}
            description={
              email.contact_source ? (
                <>
                  Adres girişimin sitesinden bulundu:{' '}
                  <Anchor href={email.contact_source} target="_blank" rel="noreferrer" size="xs">
                    kaynak
                  </Anchor>
                </>
              ) : undefined
            }
          />
          <TextInput label="Konu" size="xs" disabled={sent} value={subject} onChange={(e) => setSubject(e.currentTarget.value)} />
          <Textarea label="Metin" size="xs" disabled={sent} autosize minRows={8} maxRows={18} value={body} onChange={(e) => setBody(e.currentTarget.value)} />
          <Group justify="space-between" gap="xs">
            <Text size="xs" c="dimmed">
              Needle e-posta göndermez; kendi e-postanızdan gönderip burada işaretleyin.
            </Text>
            <Group gap="xs">
              {!sent && (
                <Button
                  size="xs"
                  variant="default"
                  disabled={!dirty}
                  loading={busy}
                  onClick={() => run(() => api.saveIntroEmail(intro.id, { to: to.trim() || null, subject, body }), 'Taslak kaydedildi')}
                >
                  Kaydet
                </Button>
              )}
              <CopyButton value={`Kime: ${to}\nKonu: ${subject}\n\n${body}`}>
                {({ copied, copy }) => (
                  <Button size="xs" variant="default" leftSection={copied ? <IconCheck size={14} /> : <IconCopy size={14} />} onClick={copy}>
                    {copied ? 'Kopyalandı' : 'Kopyala'}
                  </Button>
                )}
              </CopyButton>
              {!sent && (
                <Button size="xs" variant="default" component="a" href={mailto} leftSection={<IconMailForward size={14} />} disabled={!to.trim()}>
                  E-posta uygulamasında aç
                </Button>
              )}
              <Button
                size="xs"
                variant={sent ? 'default' : 'filled'}
                loading={busy}
                disabled={!sent && dirty}
                onClick={() => run(() => api.markIntroEmailSent(intro.id, !sent), sent ? 'İşaret kaldırıldı' : 'Gönderildi olarak işaretlendi')}
              >
                {sent ? 'İşareti kaldır' : 'Gönderildi olarak işaretle'}
              </Button>
            </Group>
          </Group>
          {!sent && dirty && (
            <Text size="xs" c="dimmed" ta="right">
              İşaretlemeden önce değişiklikleri kaydedin.
            </Text>
          )}
        </Stack>
      </Collapse>
    </div>
  )
}
