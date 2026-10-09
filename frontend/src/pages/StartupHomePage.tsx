import {
  Alert,
  Anchor,
  Button,
  Grid,
  Group,
  SimpleGrid,
  Stack,
  Text,
  UnstyledButton,
} from "@mantine/core";
import {
  IconBuildingCommunity,
  IconBuildingStore,
  IconInfoCircle,
} from "@tabler/icons-react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth";
import { StartupRecommendationsSection } from "../components/Recommendations";
import {
  PageHeader,
  PageLoader,
  SectionCard,
  StatStrip,
  Tag,
} from "../components/ui";
import { useAppData } from "../data";
import { TAG_COLOR, timeAgo } from "../labels";

export default function StartupHomePage() {
  const { me } = useAuth();
  const { introductions, calls, pilots } = useAppData();
  if (!introductions || !calls || !pilots) return <PageLoader />;

  const verified = !!me?.startup?.verified;
  const waiting = introductions.filter((i) => i.status === "bekliyor");
  const openCalls = calls.filter(
    (c) => c.status === "acik" && !c.my_application,
  );
  const active = pilots.filter((p) => p.status === "active");

  return (
    <>
      <PageHeader
        eyebrow="Girişim"
        title={me?.startup?.name ?? "Hoş geldiniz"}
        description="Kurumlardan gelen tanıştırma istekleri, başvurabileceğiniz açık çağrılar ve süren pilotlarınız."
        actions={
          <Button
            component={Link}
            to={me?.startup ? "/profil" : "/profil-bagla"}
            variant="default"
          >
            {me?.startup ? "Profili düzenle" : "Profilimi bağla"}
          </Button>
        }
      />
      {!verified && (
        <Alert
          variant="light"
          color="gray"
          icon={<IconInfoCircle size={18} />}
          mb="lg"
          title={
            me?.startup ? "Profiliniz onay bekliyor" : "Profilinizi bağlayın"
          }
        >
          <Stack gap="xs" align="flex-start">
            <Text size="sm">
              {me?.startup
                ? `${me.startup.name} profili program yöneticisinin onayında. Onaylanınca tanıştırma isteklerini görür, açık çağrılara başvurursunuz.`
                : "Havuzdaki profilinizi sahiplenin ya da yeni profil açın; onaylanınca kurumlardan gelen istekleri görürsünüz. O zamana kadar kurumları, diğer girişimleri ve açık çağrıları inceleyebilirsiniz."}
            </Text>
            {!me?.startup && (
              <Button size="xs" component={Link} to="/profil-bagla">
                Profilimi bağla
              </Button>
            )}
          </Stack>
        </Alert>
      )}
      {me?.startup && <StartupRecommendationsSection />}
      <SimpleGrid cols={{ base: 1, sm: 2 }} mb="lg">
        <UnstyledButton component={Link} to="/kurumlar" display="block">
          <SectionCard
            title="Kurumlar"
            description="Çözüm arayan firmalar, ne iş yaptıkları ve açık çağrıları"
            padding="0"
          >
            <Group gap="sm" p="md">
              <IconBuildingStore size={20} stroke={1.5} />
              <Text size="sm">Talep tarafını tanıyın</Text>
            </Group>
          </SectionCard>
        </UnstyledButton>
        <UnstyledButton component={Link} to="/girisimler" display="block">
          <SectionCard
            title="Girişimler"
            description="Havuzdaki diğer girişimler ve yetkinlikleri"
            padding="0"
          >
            <Group gap="sm" p="md">
              <IconBuildingCommunity size={20} stroke={1.5} />
              <Text size="sm">Ekosistemi keşfedin</Text>
            </Group>
          </SectionCard>
        </UnstyledButton>
      </SimpleGrid>
      <StatStrip
        items={[
          {
            label: "Bekleyen davet",
            value: waiting.length,
            tone: waiting.length ? "alert" : undefined,
          },
          { label: "Açık çağrı", value: openCalls.length },
          { label: "Aktif pilot", value: active.length },
        ]}
      />
      <Grid gap="lg">
        <Grid.Col span={{ base: 12, md: 6 }}>
          <SectionCard
            title="Tanıştırma istekleri"
            action={
              <Anchor component={Link} to="/tanistirmalar" size="sm">
                Tümü
              </Anchor>
            }
            padding="0"
          >
            {waiting.length === 0 ? (
              <Text size="sm" c="dimmed" p="lg">
                Bekleyen istek yok. Kurumlar ihtiyaçları için sizi seçtiğinde
                burada görünür.
              </Text>
            ) : (
              waiting.map((i) => (
                <UnstyledButton
                  key={i.id}
                  component={Link}
                  to="/tanistirmalar"
                  className="app-list-row"
                  display="block"
                  px="lg"
                  py="sm"
                >
                  <Text fw={500}>{i.brief.title}</Text>
                  <Text size="xs" c="dimmed">
                    {i.organization ?? "Kurum"} · {timeAgo(i.created_at)}
                  </Text>
                </UnstyledButton>
              ))
            )}
          </SectionCard>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <SectionCard
            title="Açık çağrılar"
            action={
              <Anchor component={Link} to="/cagrilar" size="sm">
                Tümü
              </Anchor>
            }
            padding="0"
          >
            {openCalls.length === 0 ? (
              <Text size="sm" c="dimmed" p="lg">
                Şu an başvurulabilir çağrı yok.
              </Text>
            ) : (
              openCalls.slice(0, 6).map((c) => (
                <UnstyledButton
                  key={c.id}
                  component={Link}
                  to={`/cagrilar/${c.id}`}
                  className="app-list-row"
                  display="block"
                  px="lg"
                  py="sm"
                >
                  <Group justify="space-between" wrap="nowrap">
                    <Stack gap={0} style={{ minWidth: 0 }}>
                      <Text fw={500} truncate>
                        {c.title}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {c.organization ?? "Kurum adı gizli"} ·{" "}
                        {timeAgo(c.created_at)}
                      </Text>
                    </Stack>
                    {c.sector && <Tag color={TAG_COLOR.slate}>{c.sector}</Tag>}
                  </Group>
                </UnstyledButton>
              ))
            )}
          </SectionCard>
        </Grid.Col>
      </Grid>
    </>
  );
}
