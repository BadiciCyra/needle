import { Anchor, Button, Card, Group, Stack, Text } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useState } from 'react'

import { api } from '../api'
import StartupDrawer from '../components/StartupDrawer'
import { EmptyState, OrgAvatar, PageHeader, PageLoader, Tag } from '../components/ui'
import { useAppData } from '../data'
import { TAG_COLOR, timeAgo } from '../labels'
import type { Claim, StartupProfile } from '../types'

// Program yöneticisi: alan adıyla doğrulanamayan sahiplenmeler ve havuza girmek isteyen yeni profiller
export default function ClaimsPage() {
  const { claims, refresh } = useAppData()
  const [busy, setBusy] = useState<number | null>(null)
  const [drawer, setDrawer] = useState<StartupProfile | null>(null)
  if (!claims) return <PageLoader />

  const act = async (claim: Claim, approve: boolean) => {
    setBusy(claim.user_id)
    try {
      await (approve ? api.approveClaim(claim.user_id) : api.rejectClaim(claim.user_id))
      await refresh()
      notifications.show({ color: 'teal', message: approve ? `${claim.startup.name} onaylandı.` : 'İstek reddedildi.' })
    } catch (e) {
      notifications.show({ color: 'red', title: 'Kaydedilemedi', message: (e as Error).message })
    } finally {
      setBusy(null)
    }
  }

  return (
    <>
      <PageHeader
        title="Girişim hesapları"
        description="Profil sahiplenme istekleri ve havuza girmek isteyen yeni profiller. E-posta henüz doğrulanmadığı için alan adı eşleşmesi tek başına kanıt değildir; gerekirse girişimle iletişime geçin. Onaylanan yeni profil eşleştirmeye hemen katılır."
      />
      {claims.length === 0 ? (
        <EmptyState title="Onay bekleyen yok" description="Yeni istekler geldikçe burada görünür." />
      ) : (
        <Stack gap="md">
          {claims.map((c) => (
            <Card key={c.user_id}>
              <Group justify="space-between" wrap="wrap" gap="md">
                <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
                  <OrgAvatar name={c.startup.name} size={40} />
                  <div style={{ minWidth: 0 }}>
                    <Group gap="xs">
                      <Anchor component="button" fw={600} c="var(--app-ink)" onClick={() => setDrawer(c.startup)}>
                        {c.startup.name}
                      </Anchor>
                      <Tag color={c.kind === 'yeni_profil' ? TAG_COLOR.slate : TAG_COLOR.ochre}>
                        {c.kind === 'yeni_profil' ? 'Yeni profil' : 'Sahiplenme'}
                      </Tag>
                    </Group>
                    <Text size="sm" c="dimmed">
                      {c.user_name} · {c.email} · {timeAgo(c.created_at)}
                    </Text>
                    <Text size="xs" c="dimmed">
                      Site: {c.startup.website ?? 'yok'}
                      {c.kind === 'sahiplenme' && (c.domain_match ? ' · e-posta alan adı siteyle eşleşiyor' : ' · e-posta alan adı siteyle eşleşmiyor')}
                    </Text>
                  </div>
                </Group>
                <Group gap="xs">
                  <Button variant="default" size="xs" loading={busy === c.user_id} onClick={() => act(c, false)}>
                    Reddet
                  </Button>
                  <Button size="xs" loading={busy === c.user_id} onClick={() => act(c, true)}>
                    Onayla
                  </Button>
                </Group>
              </Group>
            </Card>
          ))}
        </Stack>
      )}
      <StartupDrawer startup={drawer} onClose={() => setDrawer(null)} />
    </>
  )
}
