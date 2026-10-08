import {
  Alert,
  Anchor,
  Box,
  Button,
  Checkbox,
  Group,
  List,
  Modal,
  PasswordInput,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { IconAlertCircle, IconArrowRight } from '@tabler/icons-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { api } from '../api'
import { useAuth } from '../auth'
import { StitchLoader } from '../components/StitchLoader'

function AuthLayout({ title, subtitle, children }: { title: string; subtitle: ReactNode; children: ReactNode }) {
  return (
    <SimpleGrid cols={{ base: 1, md: 2 }} spacing={0} mih="100vh">
      <Box visibleFrom="md" p={56} style={{ background: '#1a1916', color: '#f4f1ea', display: 'flex', flexDirection: 'column' }}>
        <Group gap={10}>
          <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden>
            <path d="M6 27 L24 5" stroke="#f4f1ea" strokeWidth="2.4" strokeLinecap="square" />
            <path d="M22 8 C 13 11, 28 18, 10 25" fill="none" stroke="var(--mantine-color-thread-6)" strokeWidth="1.8" />
          </svg>
          <Text className="app-display" fz={28} c="#f6f3ec">
            needle
          </Text>
        </Group>
        <Box mt="auto" maw={460}>
          <Text className="app-display" fz={46} lh={1.05} c="#f6f3ec">
            Sorununuzu yazın; doğru girişimi gerekçesiyle bulalım.
          </Text>
          <Text mt="lg" c="#b9b4a8" lh={1.6}>
            Dağınık bir ihtiyaç cümlesi yeter. Needle onu netleştirir, Türkiye’deki girişimler arasından uygun olanları
            neden uygun olduklarıyla listeler ve pilotu sessizce ölmeden takip eder.
          </Text>
          <Box mt={40} style={{ ['--app-ink' as string]: '#f4f1ea', ['--app-surface' as string]: '#1a1916', ['--app-border' as string]: '#3a3833' }}>
            <StitchLoader width={220} label="Needle" />
          </Box>
        </Box>
      </Box>

      <Box p={{ base: 'lg', sm: 56 }} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Box w="100%" maw={400}>
          <Text className="app-display" fz={26} hiddenFrom="md" mb="xl">
            needle
          </Text>
          <Title order={1} className="app-display">
            {title}
          </Title>
          <Text c="dimmed" size="sm" mt={6} mb="xl">
            {subtitle}
          </Text>
          {children}
        </Box>
      </Box>
    </SimpleGrid>
  )
}

function ErrorBox({ error }: { error: string | null }) {
  return error ? (
    <Alert color="red" variant="light" icon={<IconAlertCircle size={18} />}>
      {error}
    </Alert>
  ) : null
}

export function LoginPage() {
  const { login } = useAuth()
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout
      title="Giriş yapın"
      subtitle={
        <>
          Hesabınız yok mu?{' '}
          <Anchor component={Link} to="/kayit" c="var(--app-ink)" td="underline">
            Hesap açın
          </Anchor>
        </>
      }
    >
      <form onSubmit={submit}>
        <Stack>
          <TextInput label="E-posta" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.currentTarget.value)} />
          <PasswordInput label="Şifre" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.currentTarget.value)} />
          <Anchor component={Link} to="/sifremi-unuttum" size="xs" c="dimmed" td="underline" mt={-8}>
            Şifremi unuttum
          </Anchor>
          {params.get('sifirlandi') && !error && (
            <Alert color="teal" variant="light">
              Şifreniz değişti. Yeni şifrenizle giriş yapın.
            </Alert>
          )}
          <ErrorBox error={error} />
          <Button type="submit" loading={busy} rightSection={<IconArrowRight size={15} />} mt="xs">
            Giriş yap
          </Button>
        </Stack>
      </form>
    </AuthLayout>
  )
}

function KvkkText() {
  return (
    <Stack gap="sm">
      <Alert color="yellow" variant="light" title="Taslak metin">
        Bu metin bir taslaktır ve yayına alınmadan önce hukuki inceleme gerektirir.
      </Alert>
      <Text size="sm">
        Needle, hesabınızı yönetmek ve ihtiyaçlarınızı girişimlerle eşleştirmek için aşağıdaki verileri işler:
      </Text>
      <List size="sm" spacing={4}>
        <List.Item>Ad soyad ve e-posta adresi (hesap ve iletişim)</List.Item>
        <List.Item>Kurum adı ve firma profili (eşleştirmenin isabeti)</List.Item>
        <List.Item>Girdiğiniz ihtiyaç metinleri ve verdiğiniz kararlar (eşleştirme ve pilot takibi)</List.Item>
        <List.Item>Girişim hesaplarında şirket profili, başvuru notları ve tanıştırma cevapları</List.Item>
      </List>
      <Text size="sm">
        Tanıştırma kabul edildiğinde ihtiyacın özeti ve tarafların notları karşı tarafla paylaşılır. Açık çağrılarda
        kurum adı, kurum isterse gizlenir.
      </Text>
      <Text size="sm">
        İhtiyaç metinleri, yapılandırılmış brief ve gerekçe üretmek için bir yapay zeka hizmet sağlayıcısına (Google
        Gemini) gönderilir. Şifreniz geri döndürülemez biçimde (argon2) saklanır. Verilerinizin silinmesini veya bir
        kopyasını talep edebilirsiniz.
      </Text>
    </Stack>
  )
}

export function RegisterPage() {
  const { register } = useAuth()
  const [form, setForm] = useState({ name: '', email: '', password: '', organization_name: '' })
  const [accountType, setAccountType] = useState<'firma' | 'girisim'>('firma')
  const isStartup = accountType === 'girisim'
  const [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [kvkkOpen, kvkk] = useDisclosure(false)
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [key]: e.currentTarget.value })

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await register({
        ...form,
        account_type: accountType,
        organization_name: isStartup ? null : form.organization_name,
        kvkk_onay: consent,
      })
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout
      title={isStartup ? 'Girişim hesabı açın' : 'Firma hesabı açın'}
      subtitle={
        <>
          Zaten hesabınız var mı?{' '}
          <Anchor component={Link} to="/giris" c="var(--app-ink)" td="underline">
            Giriş yapın
          </Anchor>
        </>
      }
    >
      <form onSubmit={submit}>
        <Stack>
          <SegmentedControl
            fullWidth
            value={accountType}
            onChange={(v) => setAccountType(v as 'firma' | 'girisim')}
            data={[
              { value: 'firma', label: 'Çözüm arıyorum (firma)' },
              { value: 'girisim', label: 'Çözüm sunuyorum (girişim)' },
            ]}
          />
          {isStartup ? (
            <Text size="xs" c="dimmed" lh={1.5}>
              Hesabı açtıktan sonra havuzdaki profilinizi sahiplenir ya da yeni profil oluşturursunuz. Program yöneticisi
              onayladığında kurumlardan gelen istekleri görmeye başlarsınız.
            </Text>
          ) : (
            <TextInput label="Kurum adı" required value={form.organization_name} onChange={set('organization_name')} />
          )}
          <TextInput label="Adınız soyadınız" autoComplete="name" required value={form.name} onChange={set('name')} />
          <TextInput label={isStartup ? 'Şirket e-postası' : 'İş e-postası'} type="email" autoComplete="email" required value={form.email} onChange={set('email')} />
          <PasswordInput
            label="Şifre"
            description="En az 10 karakter"
            autoComplete="new-password"
            required
            minLength={10}
            value={form.password}
            onChange={set('password')}
          />
          {/* Etikette bağlantı olursa tıklamayı yutar ve kutunun erişilebilir adı bozulur; bağlantı ayrı durur */}
          <div>
            <Checkbox checked={consent} onChange={(e) => setConsent(e.currentTarget.checked)} label="Aydınlatma metnini okudum." />
            <Anchor component="button" type="button" size="xs" c="dimmed" td="underline" ml={30} onClick={kvkk.open}>
              Metni oku
            </Anchor>
          </div>
          <ErrorBox error={error} />
          <Button type="submit" loading={busy} disabled={!consent} rightSection={<IconArrowRight size={15} />} mt="xs">
            Hesabı aç
          </Button>
        </Stack>
      </form>
      <Modal opened={kvkkOpen} onClose={kvkk.close} title="Aydınlatma metni" size="lg">
        <KvkkText />
      </Modal>
    </AuthLayout>
  )
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.requestPasswordReset(email)
      setSent(true)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout
      title="Şifremi unuttum"
      subtitle={
        <Anchor component={Link} to="/giris" c="var(--app-ink)" td="underline">
          Girişe dön
        </Anchor>
      }
    >
      {sent ? (
        // Adres kayıtlı olsun olmasın aynı mesaj: hangi e-postaların hesabı olduğu sızmaz
        <Alert color="gray" variant="light">
          Bu adresle bir hesap varsa şifre sıfırlama bağlantısı gönderildi. Bağlantı 60 dakika geçerli. E-posta
          gelmediyse gereksiz klasörüne bakın.
        </Alert>
      ) : (
        <form onSubmit={submit}>
          <Stack>
            <TextInput label="E-posta" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.currentTarget.value)} />
            <ErrorBox error={error} />
            <Button type="submit" loading={busy} rightSection={<IconArrowRight size={15} />}>
              Sıfırlama bağlantısı gönder
            </Button>
          </Stack>
        </form>
      )}
    </AuthLayout>
  )
}

export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { logout } = useAuth()
  const token = params.get('anahtar') ?? ''
  const [password, setPassword] = useState('')
  const [again, setAgain] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (password !== again) return setError('Şifreler aynı değil')
    setBusy(true)
    setError(null)
    try {
      await api.confirmPasswordReset(token, password)
      await logout() // bütün oturumlar sunucuda düştü; bu sekme de giriş ekranına döner
      navigate('/giris?sifirlandi=1', { replace: true })
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout title="Yeni şifre belirleyin" subtitle="Kaydettiğinizde açık olan bütün oturumlarınız kapanır.">
      {!token ? (
        <Alert color="red" variant="light">
          Bağlantı eksik. E-postadaki bağlantıyı tam olarak açın ya da{' '}
          <Anchor component={Link} to="/sifremi-unuttum">
            yeni bağlantı isteyin
          </Anchor>
          .
        </Alert>
      ) : (
        <form onSubmit={submit}>
          <Stack>
            <PasswordInput label="Yeni şifre" description="En az 10 karakter" autoComplete="new-password" required minLength={10} value={password} onChange={(e) => setPassword(e.currentTarget.value)} />
            <PasswordInput label="Yeni şifre (tekrar)" autoComplete="new-password" required value={again} onChange={(e) => setAgain(e.currentTarget.value)} />
            <ErrorBox error={error} />
            <Button type="submit" loading={busy} disabled={password.length < 10} rightSection={<IconArrowRight size={15} />}>
              Şifreyi kaydet
            </Button>
          </Stack>
        </form>
      )}
    </AuthLayout>
  )
}
