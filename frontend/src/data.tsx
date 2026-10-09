import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api } from './api'
import { useAuth } from './auth'
import type { Claim, Health, Introduction, NeedSummary, OpenCall, Pilot, StartupProfile } from './types'

interface AppData {
  needs: NeedSummary[] | null
  pilots: Pilot[] | null
  startups: StartupProfile[] | null
  introductions: Introduction[] | null
  calls: OpenCall[] | null
  claims: Claim[] | null
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
  const [introductions, setIntroductions] = useState<Introduction[] | null>(null)
  const [calls, setCalls] = useState<OpenCall[] | null>(null)
  const [claims, setClaims] = useState<Claim[] | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [apiDown, setApiDown] = useState(false)
  const { me } = useAuth()
  const role = me?.role
  const startupReady = role !== 'girisim' || !!me?.startup?.verified

  const refresh = useCallback(async () => {
    try {
      const [h, n, p, i, c, cl] = await Promise.all([
        api.health(),
        role === 'girisim' ? Promise.resolve([]) : api.listNeeds(),
        startupReady ? api.pilots() : Promise.resolve([]),
        startupReady ? api.introductions() : Promise.resolve([]),
        api.calls(),
        role === 'yonetici' ? api.claims() : Promise.resolve([]),
      ])
      setHealth(h)
      setNeeds(n)
      setPilots(p)
      setIntroductions(i)
      setCalls(c)
      setClaims(cl)
      setApiDown(false)
    } catch {
      setApiDown(true)
    }
  }, [role, startupReady])

  useEffect(() => {
    refresh()
    api.startups().then(setStartups).catch(() => setApiDown(true))
  }, [refresh])

  const setPilot = useCallback(
    (pilot: Pilot) => setPilots((all) => (all ? all.map((p) => (p.id === pilot.id ? pilot : p)) : all)),
    [],
  )

  const value = useMemo(
    () => ({ needs, pilots, startups, introductions, calls, claims, health, apiDown, refresh, setPilot }),
    [needs, pilots, startups, introductions, calls, claims, health, apiDown, refresh, setPilot],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAppData() {
  const value = useContext(Ctx)
  if (!value) throw new Error('useAppData AppDataProvider içinde kullanılmalı')
  return value
}
