import { Divider, Drawer, Group, List, SimpleGrid, Stack, Text, Title } from '@mantine/core'

import { MATURITY_LABEL } from '../labels'
import type { StartupProfile } from '../types'
import { MetaItem, OrgAvatar } from './ui'

export default function StartupDrawer({ startup, onClose }: { startup: StartupProfile | null; onClose: () => void }) {
  return (
    <Drawer opened={startup !== null} onClose={onClose} title="Girişim profili" size="md">
      {startup && (
        <Stack gap="lg">
          <Group gap="md" wrap="nowrap">
            <OrgAvatar name={startup.name} size={48} />
            <div>
              <Title order={2} className="app-display" fw={400} fz={32} lh={1.05}>
                {startup.name}
              </Title>
            </div>
          </Group>

          <Text size="sm" lh={1.6}>
            {startup.description}
          </Text>

          <SimpleGrid cols={3}>
            <MetaItem label="Sektör">{startup.sector}</MetaItem>
            <MetaItem label="Olgunluk">{MATURITY_LABEL[startup.maturity]}</MetaItem>
            <MetaItem label="Şehir">{startup.location}</MetaItem>
          </SimpleGrid>

          <Divider />

          <div>
            <div className="app-section-title" style={{ marginBottom: 10 }}>
              Yetkinlikler
            </div>
            <List spacing={8} size="sm" icon={<Text c="thread.7">—</Text>}>
              {startup.capabilities.map((c) => (
                <List.Item key={c}>{c}</List.Item>
              ))}
            </List>
          </div>

          {startup.past_pilots.length > 0 && (
            <div>
              <div className="app-section-title" style={{ marginBottom: 10 }}>
                Geçmiş pilotlar ve referanslar
              </div>
              <List spacing={6} size="sm" icon={<Text c="var(--app-muted)">—</Text>}>
                {startup.past_pilots.map((p) => (
                  <List.Item key={p}>{p}</List.Item>
                ))}
              </List>
            </div>
          )}
        </Stack>
      )}
    </Drawer>
  )
}
