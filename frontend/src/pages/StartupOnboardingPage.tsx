import { Alert, Box, Button, Card, Group, Stack, Tabs, Text, TextInput, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconAlertCircle, IconSearch } from '@tabler/icons-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api'
import { useAuth } from '../auth'
import StartupProfileForm from '../components/StartupProfileForm'
import { OrgAvatar } from '../components/ui'
import type { StartupProfile } from '../types'

const norm = (s: string) => s.toLocaleLowerCase('tr-TR')

// Artık uygulama kabuğunun içinde açılır (girişim doğrulanmadan da gezinebilir); üst çubuk ve çıkış kabukta
function Frame({ children }: { children: React.ReactNode }) {
  return <Box maw={760}>{children}</Box>
}

// Doğrulama bekleyen girişim: ne beklediğini ve ne yapabileceğini görür
function Pending() {
  const { me } = useAuth()
  const startup = me!.startup!
  const isNew = startup.status === 'onay_bekliyor'
  return (
    <Frame>
      <Title order={1} className="app-display" mb="xs">
        {startup.status === 'reddedildi' ? 'Profiliniz onaylanmadı' : 'Onay bekleniyor'}
      </Title>
      {startup.status === 'reddedildi' ? (
        <Alert color="red" variant="light" icon={<IconAlertCircle size={18} />}>
          Program yöneticisi {startup.name} profilini havuza almadı. Ayrıntı için program yöneticisiyle iletişime geçin.
        </Alert>
      ) : (
        <Text c="dimmed" lh={1.6}>
          {isNew
            ? `${startup.name} için açtığınız profil program yöneticisinin onayında. Onaylanınca havuza girer ve eşleştirmelerde görünür.`
            : `${startup.name} profilini sahiplenme isteğiniz program yöneticisinin onayında.`}{' '}
          Onaylanınca davetleri ve açık çağrılara başvuruları buradan yöneteceksiniz. Bu arada kurumları ve diğer
          girişimleri keşfedebilirsiniz.
        </Text>
      )}
      <Group mt="xl" gap="xs">
        <Button variant="default" onClick={() => window.location.reload()}>
          Durumu yenile
        </Button>
        <Button component={Link} to="/kurumlar" variant="default">
          Kurumları keşfet
        </Button>
      </Group>
    </Frame>
  )
}

function ClaimSearch() {
  const { setMe } = useAuth()
  const [startups, setStartups] = useState<StartupProfile[] | null>(null)
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState<string | null>(null)

  useEffect(() => {
    api.startups().then(setStartups).catch(() => setStartups([]))
  }, [])

  const results = useMemo(() => {
    const q = norm(query.trim())
    if (q.length < 2 || !startups) return []
    return startups.filter((s) => norm(s.name).includes(q) || norm(s.website ?? '').includes(q)).slice(0, 8)
  }, [query, startups])

  const claim = async (s: StartupProfile) => {
    setBusy(s.id)
    try {
      const me = await api.claimStartup(s.id)
      setMe(me)
      notifications.show({
        color: 'teal',
        message: me.startup?.verified ? `${s.name} profili hesabınıza bağlandı.` : 'İsteğiniz program yöneticisine iletildi.',
      })
    } catch (e) {
      notifications.show({ color: 'red', title: 'Sahiplenilemedi', message: (e as Error).message })
    } finally {
      setBusy(null)
    }
  }

  return (
    <Stack>
      <TextInput
        leftSection={<IconSearch size={16} />}
        placeholder="Girişim adı ya da site adresi"
        value={query}
        onChange={(e) => setQuery(e.currentTarget.value)}
        autoFocus
      />
      {query.trim().length >= 2 && results.length === 0 && (
        <Text size="sm" c="dimmed">
          Havuzda bulunamadı. “Yeni profil” sekmesinden profilinizi oluşturabilirsiniz.
        </Text>
      )}
      {results.map((s) => (
        <Card key={s.id} padding="md">
          <Group justify="space-between" wrap="nowrap">
            <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
              <OrgAvatar name={s.name} size={36} />
              <div style={{ minWidth: 0 }}>
                <Text fw={600} truncate>
                  {s.name}
                </Text>
                <Text size="xs" c="dimmed" truncate>
                  {s.sector} · {s.location}
                  {s.website ? ` · ${s.website.replace(/^https?:\/\//, '').replace(/\/$/, '')}` : ''}
                </Text>
              </div>
            </Group>
            <Button size="xs" loading={busy === s.id} onClick={() => claim(s)}>
              Bu benim
            </Button>
          </Group>
        </Card>
      ))}
    </Stack>
  )
}

export default function StartupOnboardingPage() {
  const { me, setMe } = useAuth()
  if (me?.startup && !me.startup.verified) return <Pending />

  return (
    <Frame>
      <div className="app-eyebrow" style={{ marginBottom: 10 }}>
        Girişim hesabı
      </div>
      <Title order={1} className="app-display">
        Profilinizi bağlayın
      </Title>
      <Text c="dimmed" mt={8} mb="xl" lh={1.6}>
        Needle’ın havuzunda Türkiye’deki teknoloji girişimleri kaynaklarıyla birlikte duruyor. Profiliniz varsa sahiplenin;
        böylece kurumlardan gelen tanıştırma isteklerini görür, profilinizi güncel tutarsınız. Program yöneticisi
        sahipliği onaylar; şirket e-postanız sitenizin alan adıyla eşleşiyorsa onay kolaylaşır.
      </Text>
      <Tabs defaultValue="ara" keepMounted={false}>
        <Tabs.List mb="lg">
          <Tabs.Tab value="ara">Havuzda ara</Tabs.Tab>
          <Tabs.Tab value="yeni">Yeni profil</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="ara">
          <ClaimSearch />
        </Tabs.Panel>
        <Tabs.Panel value="yeni">
          <Text size="sm" c="dimmed" mb="md">
            Yeni profiller program yöneticisinin onayından sonra havuza girer.
          </Text>
          <StartupProfileForm
            submitLabel="Profili gönder"
            onSubmit={async (profile) => {
              try {
                setMe(await api.createStartupProfile(profile))
              } catch (e) {
                notifications.show({ color: 'red', title: 'Gönderilemedi', message: (e as Error).message })
              }
            }}
          />
        </Tabs.Panel>
      </Tabs>
    </Frame>
  )
}
