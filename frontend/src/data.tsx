import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api } from './api'
import type { Health, NeedSummary, Pilot, StartupProfile } from './types'

// Uygulama genelinde paylaşılan veri: kenar çubuğu sayaçları, genel bakış ve global arama aynı kaynağı kullanır
interface AppData {
  needs: NeedSummary[] | null
  pilots: Pilot[] | null
  startups: StartupProfile[] | null
  health: Health | null
  apiDown: boolean
  refresh: () => Promise<void>
  setPilot: (pilot: Pilot) => void
}

const Ctx = createContext<AppData | null>(null)

export function AppDataProvider({ children }: { children: ReactNode }) {
  const [needs, setNeeds] = useState<NeedSummary[] | null>(null)
  const [pilots, setPilots] = useState<Pilot[] | null>(null)
  const [startups, setStartups] = useState<StartupProfile[] | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [apiDown, setApiDown] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const [h, n, p] = await Promise.all([api.health(), api.listNeeds(), api.pilots()])
      setHealth(h)
      setNeeds(n)
      setPilots(p)
      setApiDown(false)
    } catch {
      setApiDown(true)
    }
  }, [])

  useEffect(() => {
    refresh()
    api.startups().then(setStartups).catch(() => setApiDown(true))
  }, [refresh])

  const setPilot = useCallback(
    (pilot: Pilot) => setPilots((all) => (all ? all.map((p) => (p.id === pilot.id ? pilot : p)) : all)),
    [],
  )

  const value = useMemo(
    () => ({ needs, pilots, startups, health, apiDown, refresh, setPilot }),
    [needs, pilots, startups, health, apiDown, refresh, setPilot],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAppData() {
  const value = useContext(Ctx)
  if (!value) throw new Error('useAppData AppDataProvider içinde kullanılmalı')
  return value
}
