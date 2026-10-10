import { Text } from '@mantine/core'

import { withUnit } from '../labels'
import type { Metric } from '../types'

const W = 320
const H = 96
const PAD = { left: 6, right: 6, top: 10, bottom: 18 }

const day = (d: string) => new Date(d).toLocaleDateString('tr-TR', { day: 'numeric', month: 'short' })

export default function MetricChart({ metric }: { metric: Metric }) {
  const points = metric.measurements
  if (points.length === 0)
    return (
      <Text size="xs" c="dimmed">
        Henüz ölçüm yok. İlk ölçümü ekleyince gidişat burada çizilir.
      </Text>
    )

  const values = points.map((p) => p.value)
  const refs = [metric.target, metric.baseline].filter((v): v is number => v !== null)
  let lo = Math.min(...values, ...refs)
  let hi = Math.max(...values, ...refs)
  if (lo === hi) {
    lo -= 1
    hi += 1
  }
  const span = hi - lo
  lo -= span * 0.1
  hi += span * 0.1

  const x = (i: number) => PAD.left + (points.length === 1 ? (W - PAD.left - PAD.right) / 2 : (i / (points.length - 1)) * (W - PAD.left - PAD.right))
  const y = (v: number) => PAD.top + (1 - (v - lo) / (hi - lo)) * (H - PAD.top - PAD.bottom)
  const line = points.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(' ')

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img" aria-label={`${metric.name} ölçümleri`} style={{ display: 'block' }}>
      {metric.target !== null && (
        <g>
          <line x1={PAD.left} x2={W - PAD.right} y1={y(metric.target)} y2={y(metric.target)} stroke="var(--app-accent)" strokeDasharray="4 3" strokeWidth={1} />
          <text x={W - PAD.right} y={y(metric.target) - 3} textAnchor="end" fontSize={9} fill="var(--app-accent-text)">
            hedef {withUnit(metric.target, metric.unit)}
          </text>
        </g>
      )}
      {metric.baseline !== null && (
        <line x1={PAD.left} x2={W - PAD.right} y1={y(metric.baseline)} y2={y(metric.baseline)} stroke="var(--app-border-strong)" strokeDasharray="2 3" strokeWidth={1} />
      )}
      <path d={line} fill="none" stroke="var(--app-ink)" strokeWidth={1.6} />
      {points.map((p, i) => (
        <circle key={p.id} cx={x(i)} cy={y(p.value)} r={2.8} fill="var(--app-surface)" stroke="var(--app-ink)" strokeWidth={1.4}>
          <title>
            {day(p.measured_on)}: {withUnit(p.value, metric.unit)}
            {p.note ? ` · ${p.note}` : ''}
          </title>
        </circle>
      ))}
      <text x={PAD.left} y={H - 4} fontSize={9} fill="var(--app-muted)">
        {day(points[0]!.measured_on)}
      </text>
      {points.length > 1 && (
        <text x={W - PAD.right} y={H - 4} textAnchor="end" fontSize={9} fill="var(--app-muted)">
          {day(points[points.length - 1]!.measured_on)}
        </text>
      )}
    </svg>
  )
}
