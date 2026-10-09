import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api, ApiError, setUnauthorizedHandler, type RegisterBody } from './api'
import type { Me, OrgProfile } from './types'

interface AuthState {
  me: Me | null
  loading: boolean
  isAdmin: boolean
  isStartup: boolean
  setMe: (me: Me) => void
  login: (email: string, password: string) => Promise<void>
  register: (body: RegisterBody) => Promise<void>
  logout: () => Promise<void>
  saveProfile: (profile: OrgProfile) => Promise<void>
}

const Ctx = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api
      .me()
      .then(setMe)
      .catch((e) => {
        if (!(e instanceof ApiError && e.status === 401)) console.error(e)
      })
      .finally(() => setLoading(false))
    setUnauthorizedHandler(() => setMe(null))
    return () => setUnauthorizedHandler(null)
  }, [])

  const login = useCallback(async (email: string, password: string) => setMe(await api.login(email, password)), [])
  const register = useCallback(async (body: RegisterBody) => setMe(await api.register(body)), [])
  const logout = useCallback(async () => {
    await api.logout().catch(() => undefined)
    setMe(null)
  }, [])
  const saveProfile = useCallback(async (profile: OrgProfile) => setMe(await api.saveProfile(profile)), [])

  const value = useMemo(
    () => ({
      me,
      loading,
      isAdmin: me?.role === 'yonetici',
      isStartup: me?.role === 'girisim',
      setMe,
      login,
      register,
      logout,
      saveProfile,
    }),
    [me, loading, login, register, logout, saveProfile],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAuth() {
  const value = useContext(Ctx)
  if (!value) throw new Error('useAuth AuthProvider içinde kullanılmalı')
  return value
}
