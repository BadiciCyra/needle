import { Card } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useEffect, useState } from 'react'

import { api } from '../api'
import StartupProfileForm, { toInput } from '../components/StartupProfileForm'
import { PageHeader, PageLoader } from '../components/ui'
import type { StartupProfile } from '../types'

export default function StartupProfilePage() {
  const [profile, setProfile] = useState<StartupProfile | null>(null)

  useEffect(() => {
    api.myStartupProfile().then(setProfile)
  }, [])

  if (!profile) return <PageLoader />
  return (
    <>
      <PageHeader
        eyebrow="Girişim profili"
        title={profile.name}
        description="Kurumların ihtiyaçlarıyla eşleştirme bu bilgilerle yapılır. Yetkinlikleri somut tutun; değişiklik bir sonraki eşleştirmeden itibaren geçerli olur."
      />
      <Card maw={760}>
        <StartupProfileForm
          key={profile.id}
          initial={toInput(profile)}
          submitLabel="Kaydet"
          onSubmit={async (input) => {
            try {
              setProfile(await api.updateStartupProfile(input))
              notifications.show({ color: 'teal', message: 'Profil güncellendi.' })
            } catch (e) {
              notifications.show({ color: 'red', title: 'Kaydedilemedi', message: (e as Error).message })
            }
          }}
        />
      </Card>
    </>
  )
}
