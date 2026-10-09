import {
  ActionIcon,
  AppShell,
  Box,
  Burger,
  Button,
  Group,
  NavLink,
  ScrollArea,
  Text,
  Tooltip,
  UnstyledButton,
  useComputedColorScheme,
  useMantineColorScheme,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { Spotlight, spotlight, type SpotlightActionGroupData } from '@mantine/spotlight'
import {
  IconApi,
  IconBuildingCommunity,
  IconBuildingSkyscraper,
  IconBuildingStore,
  IconChartBar,
  IconFileDescription,
  IconHeartHandshake,
  IconKey,
  IconSpeakerphone,
  IconUserCheck,
  IconLayoutDashboard,
  IconLogout,
  IconMoon,
  IconPlus,
  IconRocket,
  IconSearch,
  IconSun,
} from '@tabler/icons-react'
import { useMemo } from 'react'
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

import { AuthProvider, useAuth } from './auth'
import { StitchLoader } from './components/StitchLoader'
import { AppDataProvider, useAppData } from './data'
import { ForgotPasswordPage, LoginPage, RegisterPage, ResetPasswordPage } from './pages/AuthPages'
import PasswordModal from './components/PasswordModal'
import RequireVerified from './components/RequireVerified'
import BriefPage from './pages/BriefPage'
import CallDetailPage from './pages/CallDetailPage'
import CallsPage from './pages/CallsPage'
import ClaimsPage from './pages/ClaimsPage'
import DashboardPage from './pages/DashboardPage'
import IntroductionsPage from './pages/IntroductionsPage'
import EcosystemPage from './pages/EcosystemPage'
import NeedsPage from './pages/NeedsPage'
import NewNeedPage from './pages/NewNeedPage'
import OnboardingPage from './pages/OnboardingPage'
import OrganizationsPage from './pages/OrganizationsPage'
import PilotsPage from './pages/PilotsPage'
import ReportPage from './pages/ReportPage'
import StartupHomePage from './pages/StartupHomePage'
import StartupOnboardingPage from './pages/StartupOnboardingPage'
import StartupProfilePage from './pages/StartupProfilePage'

function Logo({ light = false }: { light?: boolean }) {
  return (
    <Group gap={10} wrap="nowrap" align="center">
      <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden>
        <path d="M6 27 L24 5" stroke={light ? '#f4f1ea' : 'currentColor'} strokeWidth="2.4" strokeLinecap="square" />
        <path d="M22 8 C 13 11, 28 18, 10 25" fill="none" stroke="var(--mantine-color-thread-6)" strokeWidth="1.8" />
      </svg>
      <Text className="app-display" fz={26} lh={1} c={light ? '#f6f3ec' : undefined}>
        needle
      </Text>
    </Group>
  )
}

function AccountCard() {
  const { me, logout } = useAuth()
  const [passwordOpen, password] = useDisclosure(false)
  if (!me) return null
  return (
    <Box px={14} py={12} style={{ borderTop: '1px solid rgba(255,255,255,0.08)' }}>
      <Group justify="space-between" wrap="nowrap" gap="xs">
        <div style={{ minWidth: 0 }}>
          <Text size="sm" c="#f4f1ea" fw={500} truncate>
            {me.role === 'yonetici' ? 'Program yöneticisi' : me.role === 'girisim' ? me.startup?.name ?? 'Girişim hesabı' : me.organization?.name}
          </Text>
          <Text size="xs" c="#9a958a" truncate>
            {me.name}
          </Text>
        </div>
        <Group gap={2} wrap="nowrap">
          <Tooltip label="Şifre değiştir">
            <ActionIcon variant="subtle" className="app-nav-icon" onClick={password.open} aria-label="Şifre değiştir">
              <IconKey size={17} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label="Çıkış yap">
            <ActionIcon variant="subtle" className="app-nav-icon" onClick={logout} aria-label="Çıkış yap">
              <IconLogout size={17} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>
      <PasswordModal opened={passwordOpen} onClose={password.close} />
    </Box>
  )
}

function SystemStatus() {
  const { health, apiDown } = useAppData()
  const ok = !!health && !apiDown
  const color = apiDown ? '#e5533d' : ok ? '#6fbf73' : '#7a756a'
  return (
    <Box px={14} py={12} style={{ borderTop: '1px solid rgba(255,255,255,0.08)' }}>
      <Group gap={8} wrap="nowrap">
        <Box w={6} h={6} style={{ background: color, flexShrink: 0 }} />
        <Text size="xs" c="#cfcabf">
          {apiDown ? 'API’ye ulaşılamıyor' : ok ? 'Çevrimiçi' : 'Bağlanıyor…'}
        </Text>
      </Group>
      {health && (
        <Text size="xs" c="#7a756a" mt={4} ff="monospace">
          {health.llm_model}
        </Text>
      )}
    </Box>
  )
}

const isActive = (pathname: string, to: string) => (to === '/' ? pathname === '/' : pathname.startsWith(to))

function Navigation({ onNavigate }: { onNavigate: () => void }) {
  const { pathname } = useLocation()
  const { needs, pilots, startups, introductions, calls, claims } = useAppData()
  const { me, isAdmin, isStartup } = useAuth()
  const openNeeds = needs?.filter((n) => n.accepted_count === 0).length
  const activePilots = pilots?.filter((p) => p.status === 'active').length
  const stale = pilots?.some((p) => p.stale)
  const waitingIntros = introductions?.filter((i) => i.status === 'bekliyor').length
  const callCount = isStartup
    ? calls?.filter((c) => c.status === 'acik' && !c.my_application).length
    : calls?.filter((c) => c.status === 'acik').length

  const item = (to: string, label: string, Icon: typeof IconRocket, right?: React.ReactNode) => (
    <NavLink
      key={to}
      component={Link}
      to={to}
      label={label}
      className="app-nav-link"
      leftSection={<Icon size={17} stroke={1.5} />}
      rightSection={right}
      active={isActive(pathname, to)}
      onClick={onNavigate}
    />
  )
  const count = (n: number | undefined, alert = false) =>
    n ? (
      <span className="app-nav-count" data-alert={alert || undefined}>
        {String(n).padStart(2, '0')}
      </span>
    ) : null

  const pilotItem = item(
    '/pilotlar',
    'Pilotlar',
    IconRocket,
    stale ? <Tooltip label="Hareketsiz pilot var">{count(activePilots, true)}</Tooltip> : count(activePilots),
  )

  if (isStartup)
    return (
      <>
        <div className="app-section-label">Çalışma alanı</div>
        {item('/', 'Genel bakış', IconLayoutDashboard)}
        {item('/tanistirmalar', 'Tanıştırma istekleri', IconHeartHandshake, count(waitingIntros, true))}
        {item('/cagrilar', 'Açık çağrılar', IconSpeakerphone, count(callCount))}
        {pilotItem}
        <div className="app-section-label">Keşfet</div>
        {item('/kurumlar', 'Kurumlar', IconBuildingStore)}
        {item('/girisimler', 'Girişimler', IconBuildingCommunity, count(startups?.length))}
        <div className="app-section-label">Hesap</div>
        {me?.startup ? item('/profil', 'Girişim profili', IconBuildingSkyscraper) : item('/profil-bagla', 'Profilimi bağla', IconBuildingSkyscraper)}
      </>
    )

  return (
    <>
      <div className="app-section-label">Çalışma alanı</div>
      {item('/', 'Genel bakış', IconLayoutDashboard)}
      {item('/ihtiyaclar', 'İhtiyaçlar', IconFileDescription, count(openNeeds))}
      {item('/tanistirmalar', 'Tanıştırmalar', IconHeartHandshake, count(waitingIntros))}
      {pilotItem}
      {item('/cagrilar', 'Açık çağrılar', IconSpeakerphone, count(callCount))}
      <div className="app-section-label">Ekosistem</div>
      {item('/ekosistem', 'Girişimler', IconBuildingCommunity, count(startups?.length))}
      {item('/kurumlar', 'Kurumlar', IconBuildingStore)}
      {isAdmin && item('/hesap-onaylari', 'Girişim hesapları', IconUserCheck, count(claims?.length, true))}
      {isAdmin && (
        <>
          <div className="app-section-label">Program</div>
          {item('/rapor', 'Rapor', IconChartBar)}
        </>
      )}
      {!isAdmin && (
        <>
          <div className="app-section-label">Hesap</div>
          {item('/profil', 'Firma profili', IconBuildingSkyscraper)}
        </>
      )}
    </>
  )
}

function GlobalSearch() {
  const navigate = useNavigate()
  const { needs, startups, calls } = useAppData()
  const { isStartup } = useAuth()
  const actions = useMemo<SpotlightActionGroupData[]>(
    () =>
      isStartup
        ? [
            {
              group: 'Sayfalar',
              actions: [
                { id: 'p-home', label: 'Genel bakış', onClick: () => navigate('/'), leftSection: <IconLayoutDashboard size={18} /> },
                { id: 'p-intro', label: 'Tanıştırma istekleri', onClick: () => navigate('/tanistirmalar'), leftSection: <IconHeartHandshake size={18} /> },
                { id: 'p-calls', label: 'Açık çağrılar', onClick: () => navigate('/cagrilar'), leftSection: <IconSpeakerphone size={18} /> },
                { id: 'p-pilots', label: 'Pilotlar', onClick: () => navigate('/pilotlar'), leftSection: <IconRocket size={18} /> },
                { id: 'p-orgs', label: 'Kurumlar', onClick: () => navigate('/kurumlar'), leftSection: <IconBuildingStore size={18} /> },
                { id: 'p-startups', label: 'Girişimler', onClick: () => navigate('/girisimler'), leftSection: <IconBuildingCommunity size={18} /> },
                { id: 'p-profile', label: 'Girişim profili', onClick: () => navigate('/profil'), leftSection: <IconBuildingSkyscraper size={18} /> },
              ],
            },
            {
              group: 'Açık çağrılar',
              actions: (calls ?? []).map((c) => ({
                id: `c-${c.id}`,
                label: c.title,
                description: c.organization ?? 'Kurum adı gizli',
                onClick: () => navigate(`/cagrilar/${c.id}`),
                leftSection: <IconSpeakerphone size={18} />,
              })),
            },
          ]
        : [
      {
        group: 'Sayfalar',
        actions: [
          { id: 'p-new', label: 'Yeni ihtiyaç oluştur', onClick: () => navigate('/ihtiyaclar/yeni'), leftSection: <IconPlus size={18} /> },
          { id: 'p-home', label: 'Genel bakış', onClick: () => navigate('/'), leftSection: <IconLayoutDashboard size={18} /> },
          { id: 'p-needs', label: 'İhtiyaçlar', onClick: () => navigate('/ihtiyaclar'), leftSection: <IconFileDescription size={18} /> },
          { id: 'p-pilots', label: 'Pilotlar', onClick: () => navigate('/pilotlar'), leftSection: <IconRocket size={18} /> },
          { id: 'p-eco', label: 'Girişimler', onClick: () => navigate('/ekosistem'), leftSection: <IconBuildingCommunity size={18} /> },
        ],
      },
      {
        group: 'İhtiyaçlar',
        actions: (needs ?? []).map((n) => ({
          id: `n-${n.brief_id}`,
          label: n.title,
          description: n.organization ?? n.raw_text,
          onClick: () => navigate(`/ihtiyaclar/${n.brief_id}`),
          leftSection: <IconFileDescription size={18} />,
        })),
      },
      {
        group: 'Girişimler',
        actions: (startups ?? []).map((s) => ({
          id: `s-${s.id}`,
          label: s.name,
          description: `${s.sector} · ${s.location} · ${s.capabilities.slice(0, 2).join(', ')}`,
          onClick: () => navigate(`/ekosistem?girisim=${s.id}`),
          leftSection: <IconBuildingCommunity size={18} />,
        })),
      },
    ],
    [needs, startups, calls, isStartup, navigate],
  )

  return (
    <Spotlight
      actions={actions}
      shortcut={['mod + K', '/']}
      limit={8}
      highlightQuery
      nothingFound="Sonuç yok"
      searchProps={{ leftSection: <IconSearch size={18} />, placeholder: 'İhtiyaç, girişim veya sayfa ara…' }}
    />
  )
}

function Shell() {
  const [opened, { toggle, close }] = useDisclosure()
  const { me, isStartup, isAdmin } = useAuth()
  const { setColorScheme } = useMantineColorScheme()
  const scheme = useComputedColorScheme('light')

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 232, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding={{ base: 'md', sm: 'xl' }}
    >
      <AppShell.Header className="app-header">
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Box hiddenFrom="sm">
              <Logo />
            </Box>
            <UnstyledButton className="app-search-trigger" onClick={() => spotlight.open()} visibleFrom="sm">
              <Group justify="space-between" wrap="nowrap" h="100%">
                <Group gap={8} wrap="nowrap">
                  <IconSearch size={16} />
                  <Text size="sm" c="dimmed">
                    Ara…
                  </Text>
                </Group>
                <Text size="xs" ff="monospace" c="var(--app-muted)">
                  Ctrl K
                </Text>
              </Group>
            </UnstyledButton>
          </Group>
          <Group gap="xs" wrap="nowrap">
            <ActionIcon variant="subtle" color="gray" size="lg" hiddenFrom="sm" onClick={() => spotlight.open()} aria-label="Ara">
              <IconSearch size={18} />
            </ActionIcon>
            <Tooltip label="API dokümanı">
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                component="a"
                href="/api/docs"
                target="_blank"
                aria-label="API dokümanı"
              >
                <IconApi size={19} />
              </ActionIcon>
            </Tooltip>
            <Tooltip label={scheme === 'dark' ? 'Açık tema' : 'Koyu tema'}>
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                onClick={() => setColorScheme(scheme === 'dark' ? 'light' : 'dark')}
                aria-label="Temayı değiştir"
              >
                {scheme === 'dark' ? <IconSun size={19} /> : <IconMoon size={19} />}
              </ActionIcon>
            </Tooltip>
            {!isStartup && (
              <Button component={Link} to="/ihtiyaclar/yeni" leftSection={<IconPlus size={15} />} size="xs" h={32} visibleFrom="xs">
                Yeni ihtiyaç
              </Button>
            )}
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar className="app-navbar">
        <AppShell.Section px={14} pt={18} pb={6} visibleFrom="sm">
          <Logo light />
          <Text size="xs" c="#7a756a" mt={6} ff="monospace">
            ihtiyaç → eşleşme → pilot
          </Text>
        </AppShell.Section>
        <AppShell.Section grow component={ScrollArea}>
          <Navigation onNavigate={close} />
        </AppShell.Section>
        <AppShell.Section>
          <AccountCard />
          <SystemStatus />
        </AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Main>
        <Box maw={1280} mx="auto">
          {isStartup ? (
            <Routes>
              <Route path="/" element={<StartupHomePage />} />
              <Route path="/tanistirmalar" element={<RequireVerified title="Tanıştırmalar"><IntroductionsPage /></RequireVerified>} />
              <Route path="/cagrilar" element={<CallsPage />} />
              <Route path="/cagrilar/:callId" element={<CallDetailPage />} />
              <Route path="/pilotlar" element={<RequireVerified title="Pilotlar"><PilotsPage /></RequireVerified>} />
              <Route path="/kurumlar" element={<OrganizationsPage />} />
              <Route path="/girisimler" element={<EcosystemPage />} />
              <Route path="/profil-bagla" element={<StartupOnboardingPage />} />
              <Route path="/profil" element={me?.startup ? <StartupProfilePage /> : <Navigate to="/profil-bagla" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          ) : (
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/ihtiyaclar" element={<NeedsPage />} />
              <Route path="/ihtiyaclar/yeni" element={<NewNeedPage />} />
              <Route path="/ihtiyaclar/:briefId" element={<BriefPage />} />
              <Route path="/tanistirmalar" element={<IntroductionsPage />} />
              <Route path="/pilotlar" element={<PilotsPage />} />
              <Route path="/cagrilar" element={<CallsPage />} />
              <Route path="/cagrilar/:callId" element={<CallDetailPage />} />
              <Route path="/ekosistem" element={<EcosystemPage />} />
              <Route path="/kurumlar" element={<OrganizationsPage />} />
              {isAdmin && <Route path="/hesap-onaylari" element={<ClaimsPage />} />}
              {isAdmin && <Route path="/rapor" element={<ReportPage />} />}
              <Route path="/profil" element={<OnboardingPage mode="edit" />} />
              <Route path="/yeni" element={<Navigate to="/ihtiyaclar/yeni" replace />} />
              <Route path="/girisimler" element={<Navigate to="/ekosistem" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          )}
        </Box>
      </AppShell.Main>
      <GlobalSearch />
    </AppShell>
  )
}

function Gate() {
  const { me, loading } = useAuth()
  const { pathname } = useLocation()
  if (pathname === '/sifre-sifirla') return <ResetPasswordPage />
  if (loading)
    return (
      <Box h="100vh" style={{ display: 'grid', placeItems: 'center' }}>
        <StitchLoader width={180} />
      </Box>
    )
  if (!me)
    return (
      <Routes>
        <Route path="/kayit" element={<RegisterPage />} />
        <Route path="/sifremi-unuttum" element={<ForgotPasswordPage />} />
        <Route path="/sifre-sifirla" element={<ResetPasswordPage />} />
        <Route path="*" element={<LoginPage />} />
      </Routes>
    )
  if (me.role === 'firma' && !me.organization?.onboarded) return <OnboardingPage mode="onboarding" />
  return (
    <AppDataProvider key={me.id}>
      <Shell />
    </AppDataProvider>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  )
}
