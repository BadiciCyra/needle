import {
  Alert,
  Anchor,
  Button,
  Card,
  Divider,
  Grid,
  Group,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  TextInput,
  Timeline,
  UnstyledButton,
} from '@mantine/core'
import { IconAlertCircle, IconArrowRight } from '@tabler/icons-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api } from '../api'
import { useAuth } from '../auth'
import { templatesFor } from '../catalog'
import { StitchProgress } from '../components/StitchLoader'
import { PageHeader } from '../components/ui'
import { useAppData } from '../data'

// backend/seed/needs.json'dan örnekler (kurgusal kurumlar)
const EXAMPLES = [
  {
    label: 'Bayi şikayetlerini sınıflandırma',
    sector: 'Perakende',
    raw_text: 'Sahadaki bayilerimizden gelen şikayetleri daha hızlı sınıflandırmak istiyoruz, çok manuel gidiyor.',
    org: { name: 'Kuzey Beyaz Eşya A.Ş.', sector: 'perakende', author_unit: 'İnovasyon Ofisi', owner_unit: 'Bayi Satış Operasyonları' },
  },
  {
    label: 'Fren diskinde yüzey hatası tespiti',
    sector: 'Otomotiv',
    raw_text:
      'Hat sonunda fren diski yüzeylerindeki çizik ve çatlakları operatörler gözle kontrol ediyor, vardiya sonuna doğru kaçırmalar artıyor. Müşteri iadelerini yarıya indirmek istiyoruz. 3 aylık bir pilotla tek hatta başlayabiliriz.',
    org: { name: 'Marmara Otomotiv Parça', sector: 'otomotiv yan sanayi', author_unit: 'Ar-Ge Müdürlüğü', owner_unit: 'Kalite Güvence' },
  },
  {
    label: 'KOBİ kredi değerlendirmesini hızlandırma',
    sector: 'Finans',
    raw_text: 'KOBİ kredi başvurularının değerlendirilmesi çok uzun sürüyor, müşteriyi kaybediyoruz.',
    org: { name: 'Birlik Katılım Bankası', sector: 'finans', author_unit: 'İnovasyon Laboratuvarı', owner_unit: 'KOBİ Kredileri' },
  },
  {
    label: 'Su şebekesinde kaçak yeri tespiti',
    sector: 'Altyapı',
    raw_text: 'Şebekede kayıp kaçak oranı yüksek ama kaçağın yerini bulmak için yolu kazmak zorunda kalıyoruz.',
    org: { name: 'Başkent Su İdaresi', sector: 'altyapı', author_unit: 'Ar-Ge Şube', owner_unit: 'Şebeke İşletme' },
  },
]

const EMPTY_ORG = { name: '', sector: '', author_unit: '', owner_unit: '' }

export default function NewNeedPage() {
  const navigate = useNavigate()
  const { refresh } = useAppData()
  const { me, isAdmin } = useAuth()
  const sector = me?.organization?.profile?.sector
  const templates = isAdmin
    ? EXAMPLES.map((e) => ({ label: e.label, text: e.raw_text, meta: `${e.sector} · ${e.org.name}`, org: e.org }))
    : templatesFor(sector).map((t) => ({ ...t, meta: sector ?? 'Genel', org: undefined }))
  const [rawText, setRawText] = useState('')
  const [org, setOrg] = useState(EMPTY_ORG)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const valid = rawText.trim().length >= 10

  const submit = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.createNeed(rawText.trim(), isAdmin && org.name.trim() ? org : undefined)
      await refresh()
      navigate(`/ihtiyaclar/${result.brief_id}`)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const field = (key: keyof typeof EMPTY_ORG, label: string, placeholder: string) => (
    <TextInput label={label} placeholder={placeholder} value={org[key]} onChange={(e) => setOrg({ ...org, [key]: e.currentTarget.value })} />
  )

  return (
    <>
      <PageHeader
        eyebrow={
          <Anchor component={Link} to="/ihtiyaclar" size="sm" c="dimmed">
            İhtiyaçlar
          </Anchor>
        }
        title="Yeni ihtiyaç"
        description="İhtiyacı kurumun kendi cümleleriyle yazın. Dağınık olması sorun değil; Needle onu yapılandırılmış bir brief’e çevirir."
      />

      <Grid gap="lg">
        <Grid.Col span={{ base: 12, md: 8 }}>
          {loading ? (
            <StitchProgress
              title="Brief hazırlanıyor"
              description="İhtiyaç metni problem, kapsam, yetkinlik ve başarı kriterine ayrılıyor; eksik bilgi varsa takip soruları hazırlanıyor. 10–40 saniye sürebilir."
            />
          ) : (
            <Card>
              <Stack gap="lg">
                <div>
                  <div className="app-section-title">İhtiyaç</div>
                  <Text size="sm" c="dimmed">
                    Problemi, etkilenen süreci ve beklentiyi anlatın. Hacim, süre ve başarı ölçütü varsa ekleyin.
                  </Text>
                </div>
                <Textarea
                  placeholder="Örn. Sahadaki bayilerimizden gelen şikayetleri daha hızlı sınıflandırmak istiyoruz, çok manuel gidiyor."
                  autosize
                  minRows={6}
                  maxRows={14}
                  value={rawText}
                  onChange={(e) => setRawText(e.currentTarget.value)}
                  description={`${rawText.trim().length} karakter`}
                  inputWrapperOrder={['input', 'description']}
                />

                {isAdmin && (
                  <>
                    <Divider />

                    <div>
                      <div className="app-section-title">Kurum</div>
                      <Text size="sm" c="dimmed">
                        İsteğe bağlı. İhtiyacı yazan birim ile yaşayan birimi ayırmak, doğru kişiyle pilot kurmayı kolaylaştırır.
                      </Text>
                    </div>
                    <SimpleGrid cols={{ base: 1, sm: 2 }}>
                      {field('name', 'Kurum adı', 'Örn. Marmara Otomotiv Parça')}
                      {field('sector', 'Sektör', 'Örn. otomotiv yan sanayi')}
                      {field('author_unit', 'İhtiyacı yazan birim', 'Örn. Ar-Ge Müdürlüğü')}
                      {field('owner_unit', 'İhtiyacı yaşayan birim', 'Örn. Kalite Güvence')}
                    </SimpleGrid>
                  </>
                )}

                {error && (
                  <Alert color="red" variant="light" icon={<IconAlertCircle size={18} />} title="Brief üretilemedi">
                    {error}
                  </Alert>
                )}

                <Group justify="flex-end" gap="sm">
                  <Button variant="default" component={Link} to="/ihtiyaclar">
                    Vazgeç
                  </Button>
                  <Button rightSection={<IconArrowRight size={15} />} loading={loading} disabled={!valid} onClick={submit}>
                    Brief’e çevir
                  </Button>
                </Group>
              </Stack>
            </Card>
          )}
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 4 }}>
          <Stack gap="lg">
            <Card>
              <Text className="app-display" fz={26} mb="md">
                Sonra ne olacak?
              </Text>
              <Timeline active={-1} bulletSize={22} lineWidth={1} color="ink">
                <Timeline.Item bullet={<Text className="app-num" fz={10}>01</Text>} title="Brief">
                  <Text size="xs" c="dimmed">
                    Problem, kapsam, gereken yetkinlikler, süre ve başarı kriteri çıkarılır.
                  </Text>
                </Timeline.Item>
                <Timeline.Item bullet={<Text className="app-num" fz={10}>02</Text>} title="Takip soruları">
                  <Text size="xs" c="dimmed">
                    Eksik bir şey varsa en fazla 3 kısa soru sorulur.
                  </Text>
                </Timeline.Item>
                <Timeline.Item bullet={<Text className="app-num" fz={10}>03</Text>} title="Gerekçeli eşleşme">
                  <Text size="xs" c="dimmed">
                    Uygun girişimler, hangi ifadenin hangi yetkinlikle örtüştüğüyle listelenir.
                  </Text>
                </Timeline.Item>
                <Timeline.Item bullet={<Text className="app-num" fz={10}>04</Text>} title="Pilot">
                  <Text size="xs" c="dimmed">
                    Kabul edilen aday için pilot kartı açılır ve takip edilir.
                  </Text>
                </Timeline.Item>
              </Timeline>
            </Card>

            <Card padding="md">
              <div className="app-section-title" style={{ marginBottom: 2 }}>
                {isAdmin ? 'Örnekle başlayın' : 'Sık görülen sorunlar'}
              </div>
              <Text size="sm" c="dimmed" mb="sm">
                {isAdmin ? 'Bir şablon seçin, formu doldurur.' : 'Size en yakın olanı seçin, sonra kendi cümlelerinizle düzenleyin.'}
              </Text>
              <Stack gap={6}>
                {templates.map((example) => (
                  <UnstyledButton
                    key={example.label}
                    onClick={() => {
                      setRawText(example.text)
                      if (example.org) setOrg(example.org)
                    }}
                    p="sm"
                    style={{ border: '1px solid var(--app-border)', borderRadius: 2 }}
                    className="app-row-link"
                  >
                    <Text size="sm" fw={500}>
                      {example.label}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {example.meta}
                    </Text>
                  </UnstyledButton>
                ))}
              </Stack>
            </Card>
          </Stack>
        </Grid.Col>
      </Grid>
    </>
  )
}
