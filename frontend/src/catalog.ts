// Firma profili seçenekleri ve sektöre göre hazır sorun şablonları

export const SECTORS = [
  'Üretim',
  'Otomotiv',
  'Perakende',
  'Enerji',
  'Lojistik',
  'Finans',
  'Sigorta',
  'Sağlık',
  'Tarım ve gıda',
  'Altyapı ve belediye',
  'Telekom',
  'İnşaat',
  'Tekstil',
  'Eğitim',
  'Kamu',
  'Diğer',
]

// Girişim havuzundaki sektör adları (backend seed ile aynı)
export const STARTUP_SECTORS = [
  'yazılım', 'üretim', 'endüstriyel IoT', 'iş güvenliği', 'enerji', 'akıllı şehir', 'lojistik', 'sağlık', 'finans',
  'sigorta', 'tarım', 'perakende', 'insan kaynakları', 'hukuk', 'eğitim', 'medya', 'siber güvenlik', 'turizm',
  'inşaat', 'savunma', 'telekom',
]

export const CITIES = ['İstanbul', 'Ankara', 'İzmir', 'Bursa', 'Kocaeli', 'Antalya', 'Konya', 'Gaziantep', 'Kayseri', 'Eskişehir', 'Diğer']

export const EMPLOYEE_RANGES = [
  { value: '1-49', label: '1–49' },
  { value: '50-249', label: '50–249' },
  { value: '250-999', label: '250–999' },
  { value: '1000+', label: '1000+' },
] as const

export const SYSTEMS = ['SAP', 'Oracle', 'Logo', 'Netsis', 'Microsoft Dynamics', 'Salesforce', 'Kendi yazılımımız', 'Excel ağırlıklı']

export const DATA_CONSTRAINTS = [
  'Veri şirket dışına çıkamaz',
  'Kişisel veri işleniyor (KVKK)',
  'Bulut kullanabiliriz',
  'Sahada internet kısıtlı',
]

export const BUDGET_RANGES = ['Henüz belli değil', '250 bin TL altı', '250 bin – 1 milyon TL', '1 milyon TL üzeri']

export const PILOT_DURATIONS = ['1 ay', '3 ay', '6 ay', '6 aydan uzun']

export interface ProblemTemplate {
  label: string
  text: string
}

// Firma bir şablonu seçip kendi cümleleriyle düzenler; Needle'ın "önce sorun, sonra eşleşme" ilkesi korunur
export const SECTOR_TEMPLATES: Record<string, ProblemTemplate[]> = {
  Üretim: [
    { label: 'Kalite kontrolde gözden kaçan hatalar', text: 'Üretim hattında ürün yüzeyindeki hataları operatörler gözle kontrol ediyor; vardiya sonuna doğru kaçırmalar artıyor.' },
    { label: 'Plansız makine duruşları', text: 'Kritik makinelerimiz beklenmedik şekilde arızalanıyor ve hat duruyor; arızaları önceden görmek istiyoruz.' },
    { label: 'Enerji tüketimi yüksek', text: 'Fabrikanın enerji tüketimi yüksek ve hangi hattın ne kadar tükettiğini anlık göremiyoruz.' },
    { label: 'İş güvenliği ihlalleri', text: 'Sahada baret ve yelek kurallarına uyulmuyor; ihlalleri ancak kaza sonrası fark ediyoruz.' },
  ],
  Otomotiv: [
    { label: 'Parça yüzey hatası tespiti', text: 'Hat sonunda parça yüzeylerindeki çizik ve çatlakları gözle kontrol ediyoruz; müşteri iadelerini azaltmak istiyoruz.' },
    { label: 'Tedarik zinciri gecikmeleri', text: 'Tedarikçi teslimatlarındaki gecikmeleri geç fark ediyoruz ve üretim planı bozuluyor.' },
    { label: 'Bayi şikayetleri', text: 'Bayilerden gelen şikayetleri elle sınıflandırıyoruz; süreç yavaş ve tutarsız.' },
    { label: 'Montaj süresi optimizasyonu', text: 'Montaj hattındaki iş adımlarının süresini ölçemiyoruz ve darboğazları bulamıyoruz.' },
  ],
  Perakende: [
    { label: 'Stok ve talep tahmini', text: 'Mağazalarda bazı ürünler sık sık tükeniyor, bazıları ise elde kalıyor; talebi daha iyi tahmin etmek istiyoruz.' },
    { label: 'Müşteri mesajlarına yanıt', text: 'WhatsApp ve web üzerinden gelen müşteri sorularına yetişemiyoruz; yanıt süreleri uzuyor.' },
    { label: 'Raf düzeni takibi', text: 'Mağaza raflarının planograma uygun olup olmadığını denetlemek çok zaman alıyor.' },
    { label: 'Bayi ve müşteri şikayetleri', text: 'Gelen şikayetleri elle okuyup sınıflandırıyoruz; çok manuel gidiyor.' },
  ],
  Enerji: [
    { label: 'Güneş santrali verimi', text: 'Güneş santrallerimizdeki verim kayıplarının nedenini geç tespit ediyoruz.' },
    { label: 'Tüketim tahmini', text: 'Elektrik tüketimini gün öncesinden doğru tahmin edemediğimiz için dengesizlik maliyeti ödüyoruz.' },
    { label: 'Saha bakım planlaması', text: 'Saha ekiplerinin bakım rotalarını elle planlıyoruz; çok zaman ve yakıt harcanıyor.' },
  ],
  Lojistik: [
    { label: 'Rota planlama', text: 'Dağıtım araçlarının rotalarını elle planlıyoruz; yakıt maliyeti ve gecikmeler artıyor.' },
    { label: 'Depo verimliliği', text: 'Depoda toplama süreleri uzun ve raf yerleşimi verimsiz.' },
    { label: 'Navlun süreçleri', text: 'Navlun teklif toplama ve taşıma takibi e-posta ve telefonla yürüyor.' },
  ],
  Finans: [
    { label: 'Kredi değerlendirme süresi', text: 'KOBİ kredi başvurularının değerlendirilmesi çok uzun sürüyor, müşteriyi kaybediyoruz.' },
    { label: 'Dolandırıcılık tespiti', text: 'Şüpheli işlemleri geç fark ediyoruz; mevcut kurallar çok fazla yanlış alarm üretiyor.' },
    { label: 'Belge işleme', text: 'Müşterilerden gelen mali tabloları ve belgeleri elle sisteme giriyoruz.' },
  ],
  Sağlık: [
    { label: 'Radyoloji iş yükü', text: 'Radyologların raporlama yükü çok fazla; kritik bulgular gecikebiliyor.' },
    { label: 'Klinik dokümantasyon', text: 'Hekimler zamanlarının büyük kısmını kayıt ve rapor yazmaya harcıyor.' },
    { label: 'Randevuya gelmeme', text: 'Hastaların bir kısmı randevuya gelmiyor; boş kalan slotları dolduramıyoruz.' },
  ],
  'Tarım ve gıda': [
    { label: 'Hastalık ve zararlı erken uyarı', text: 'Tarladaki hastalık ve zararlıları geç fark ediyoruz; ilaçlama maliyeti artıyor.' },
    { label: 'Sulama optimizasyonu', text: 'Sulamayı tecrübeye göre yapıyoruz; su ve enerji israfı oluyor.' },
    { label: 'Verim tahmini', text: 'Hasat öncesi verimi doğru tahmin edemediğimiz için satış planlaması zorlaşıyor.' },
  ],
  'Altyapı ve belediye': [
    { label: 'Su şebekesinde kaçak', text: 'Şebekede kayıp kaçak oranı yüksek ama kaçağın yerini bulmak için yolu kazmak zorunda kalıyoruz.' },
    { label: 'Atık toplama rotaları', text: 'Atık toplama araçları konteynerler dolu olsun olmasın aynı rotayı izliyor.' },
    { label: 'Otopark ve trafik', text: 'Otopark doluluğunu ve trafik yoğunluğunu anlık göremiyoruz.' },
  ],
}

// Sektöre özel şablon yoksa
export const GENERIC_TEMPLATES: ProblemTemplate[] = [
  { label: 'Elle yapılan tekrarlı işler', text: 'Ekiplerimiz tekrarlayan ofis işlerine (veri girişi, rapor hazırlama) çok zaman harcıyor.' },
  { label: 'Müşteri taleplerine yetişememe', text: 'Müşterilerden gelen taleplere zamanında yanıt veremiyoruz; talepler kanallar arasında kayboluyor.' },
  { label: 'Belgelerden veri çıkarma', text: 'Fatura, sözleşme ve formlardaki bilgileri elle sisteme aktarıyoruz.' },
  { label: 'Veriye dayalı karar', text: 'Elimizde veri var ama raporlar geç hazırlanıyor ve karar almakta kullanamıyoruz.' },
]

export const templatesFor = (sector: string | null | undefined) =>
  (sector && SECTOR_TEMPLATES[sector]) || GENERIC_TEMPLATES
