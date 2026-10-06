import { Box, Card, Center, Group, Stack, Text, Title, Tooltip } from '@mantine/core'
import type { CSSProperties, ReactNode } from 'react'

import { initials, STAGE, type Stage } from '../labels'
import { StitchLoader } from './StitchLoader'

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  eyebrow?: ReactNode
}) {
  return (
    <Group justify="space-between" align="flex-end" mb={28} wrap="wrap" gap="md">
      <div style={{ minWidth: 0 }}>
        {eyebrow && (
          <div className="app-eyebrow" style={{ marginBottom: 10 }}>
            {eyebrow}
          </div>
        )}
        <Title order={1} className="app-display">
          {title}
        </Title>
        {description && (
          <Text c="var(--app-muted)" mt={8} maw={640} size="sm" lh={1.6}>
            {description}
          </Text>
        )}
      </div>
      {actions && <Group gap="xs">{actions}</Group>}
    </Group>
  )
}

export interface Stat {
  label: string
  value: ReactNode
  hint?: ReactNode
  onClick?: () => void
  tone?: 'alert'
}

// Kart ızgarası yerine çizgilerle ayrılmış tek bir rakam şeridi
export function StatStrip({ items }: { items: Stat[] }) {
  return (
    <Box
      className="app-stats"
      mb={32}
      style={{ gridTemplateColumns: `repeat(auto-fit, minmax(${items.length > 3 ? 160 : 200}px, 1fr))` }}
    >
      {items.map((s) => (
        <div key={s.label} className="app-stat" data-clickable={s.onClick ? true : undefined} onClick={s.onClick}>
          <div className="app-label">{s.label}</div>
          <div className="app-stat-value" style={s.tone === 'alert' ? { color: 'var(--app-accent)' } : undefined}>
            {s.value}
          </div>
          {s.hint && (
            <Text size="xs" c="var(--app-muted)" mt={8}>
              {s.hint}
            </Text>
          )}
        </div>
      ))}
    </Box>
  )
}

export function Tag({ color, children, tooltip }: { color: string; children: ReactNode; tooltip?: string }) {
  const tag = (
    <span className="app-tag" style={{ '--tag-color': color } as CSSProperties}>
      {children}
    </span>
  )
  return tooltip ? <Tooltip label={tooltip}>{tag}</Tooltip> : tag
}

export function StageBadge({ stage }: { stage: Stage }) {
  const s = STAGE[stage]
  return (
    <Tag color={s.color} tooltip={s.hint}>
      {s.label}
    </Tag>
  )
}

export function SectionCard({
  title,
  description,
  action,
  children,
  padding = 'lg',
}: {
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  children: ReactNode
  padding?: string
}) {
  return (
    <Card padding={0}>
      <Group
        justify="space-between"
        px="lg"
        py="sm"
        wrap="nowrap"
        style={{ borderBottom: '1px solid var(--app-border)' }}
      >
        <div>
          <div className="app-section-title">{title}</div>
          {description && (
            <Text size="xs" c="var(--app-muted)" mt={2}>
              {description}
            </Text>
          )}
        </div>
        {action}
      </Group>
      <Box p={padding}>{children}</Box>
    </Card>
  )
}

export function OrgAvatar({ name, size = 32 }: { name: string; size?: number; color?: string }) {
  return (
    <div className="app-mono-avatar" style={{ width: size, height: size, fontSize: Math.max(10, size * 0.34) }}>
      {initials(name)}
    </div>
  )
}

export function EmptyState({ title, description, action }: { icon?: unknown; title: string; description?: ReactNode; action?: ReactNode }) {
  return (
    <Card py={56}>
      <Stack align="center" gap={6} maw={420} mx="auto" ta="center">
        <Text className="app-display" fz={28}>
          {title}
        </Text>
        {description && (
          <Text size="sm" c="var(--app-muted)" lh={1.6}>
            {description}
          </Text>
        )}
        {action && <Box mt="md">{action}</Box>}
      </Stack>
    </Card>
  )
}

export function PageLoader() {
  return (
    <Center h={320}>
      <StitchLoader width={150} />
    </Center>
  )
}

export function MetaItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="app-caption" style={{ marginBottom: 2 }}>
        {label}
      </div>
      <Text size="sm" component="div">
        {children}
      </Text>
    </div>
  )
}
