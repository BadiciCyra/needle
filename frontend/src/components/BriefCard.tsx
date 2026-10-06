import { Badge, Card, Divider, Group, SimpleGrid, Stack, Text } from '@mantine/core'

import { BRIEF_FIELD_LABEL, MATURITY_LABEL, TAG_COLOR } from '../labels'
import type { Brief } from '../types'
import { Tag } from './ui'

function Field({ name, value, missing }: { name: string; value: string | null; missing: boolean }) {
  return (
    <div>
      <div className="app-caption" style={{ marginBottom: 2 }}>
        {BRIEF_FIELD_LABEL[name] ?? name}
      </div>
      {value ? (
        <Text size="sm" lh={1.5}>
          {value}
        </Text>
      ) : missing ? (
        <Tag color={TAG_COLOR.ochre}>Eksik</Tag>
      ) : (
        <Text size="sm" c="dimmed">
          —
        </Text>
      )}
    </div>
  )
}

export default function BriefCard({ brief, rawText }: { brief: Brief; rawText?: string }) {
  const missing = new Set(brief.missing_fields)
  return (
    <Card>
      <Stack gap="md">
        <Group justify="space-between">
          <div className="app-section-title">Brief</div>
          {brief.missing_fields.length > 0 ? (
            <Tag color={TAG_COLOR.ochre}>{brief.missing_fields.length} eksik alan</Tag>
          ) : (
            <Tag color={TAG_COLOR.green}>Tamam</Tag>
          )}
        </Group>

        {rawText && (
          <Text size="sm" c="dimmed" fs="italic" lh={1.55} className="app-evidence">
            {rawText}
          </Text>
        )}

        <Field name="problem" value={brief.problem} missing={missing.has('problem')} />

        <div>
          <div className="app-caption" style={{ marginBottom: 6 }}>
            {BRIEF_FIELD_LABEL.required_capabilities}
          </div>
          {brief.required_capabilities.length ? (
            <Group gap={6}>
              {brief.required_capabilities.map((cap) => (
                <Badge key={cap} size="lg" color="ink" fw={400}>
                  {cap}
                </Badge>
              ))}
            </Group>
          ) : (
            <Tag color={TAG_COLOR.ochre}>Eksik</Tag>
          )}
        </div>

        <Divider />

        <SimpleGrid cols={2} spacing="md" verticalSpacing="md">
          <Field name="scope" value={brief.scope} missing={missing.has('scope')} />
          <Field name="success_criteria" value={brief.success_criteria} missing={missing.has('success_criteria')} />
          <Field name="timeline" value={brief.timeline} missing={missing.has('timeline')} />
          <Field name="budget" value={brief.budget} missing={false} />
          <Field name="sector" value={brief.sector} missing={false} />
          <Field name="location_preference" value={brief.location_preference} missing={false} />
          <Field name="min_maturity" value={brief.min_maturity ? MATURITY_LABEL[brief.min_maturity] : null} missing={false} />
        </SimpleGrid>
      </Stack>
    </Card>
  )
}
