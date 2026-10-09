import { Card, Stack, Text } from '@mantine/core'

const START = 14
const END = 166
const Y = 30

export function StitchLoader({ width = 180, label = 'Yükleniyor' }: { width?: number; label?: string }) {
  return (
    <svg
      className="stitch"
      width={width}
      height={(width / 180) * 48}
      viewBox="0 0 180 48"
      role="img"
      aria-label={label}
      style={{ overflow: 'visible' }}
    >
      <line x1={START} x2={END} y1={Y} y2={Y} className="stitch-fabric" />

      <g className="stitch-trail">
        <line x1={START} x2={END} y1={Y} y2={Y} className="stitch-seam" />
      </g>

      <g className="stitch-travel">
        <g className="stitch-bob">
          <path d={`M -5 ${Y - 22} C -9 ${Y - 18}, -13 ${Y - 3}, -30 ${Y}`} className="stitch-thread" />
          <line x1={-6} y1={Y - 26} x2={1} y2={Y - 1} className="stitch-needle" />
          <ellipse cx={-5} cy={Y - 22} rx={1} ry={2.6} transform={`rotate(-16 -5 ${Y - 22})`} className="stitch-eye" />
        </g>
      </g>
    </svg>
  )
}

export function StitchProgress({ title, description }: { title: string; description?: string }) {
  return (
    <Card py={48}>
      <Stack align="center" gap={6} ta="center" maw={440} mx="auto">
        <StitchLoader width={200} label={title} />
        <Text className="app-display" fz={26} mt="sm">
          {title}
        </Text>
        {description && (
          <Text size="sm" c="var(--app-muted)" lh={1.6}>
            {description}
          </Text>
        )}
      </Stack>
    </Card>
  )
}
