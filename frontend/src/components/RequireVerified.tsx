import { Button } from '@mantine/core'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '../auth'
import { EmptyState, PageHeader } from './ui'

export default function RequireVerified({ title, children }: { title: string; children: ReactNode }) {
  const { me, isStartup } = useAuth()
  if (!isStartup || me?.startup?.verified) return <>{children}</>
  const pending = !!me?.startup
  return (
    <>
      <PageHeader title={title} />
      <EmptyState
        title={pending ? 'Onay bekleniyor' : 'Önce profilinizi bağlayın'}
        description={
          pending
            ? 'Program yöneticisi profilinizi onaylayınca bu bölüm açılır. Bu arada kurumları ve diğer girişimleri keşfedebilirsiniz.'
            : 'Kurumlardan gelen istekleri görmek için havuzdaki profilinizi sahiplenin ya da yeni profil açın.'
        }
        action={
          <Button component={Link} to={pending ? '/kurumlar' : '/profil-bagla'}>
            {pending ? 'Kurumları keşfet' : 'Profilimi bağla'}
          </Button>
        }
      />
    </>
  )
}
