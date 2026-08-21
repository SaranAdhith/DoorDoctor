import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { authApi } from '../api/auth'
import { clearToken, getToken, onUnauthorized, setToken } from '../api/client'
import type { Role, User } from '../types'

interface AuthContextValue {
  user: User | null
  initialising: boolean
  login: (email: string, password: string) => Promise<User>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export const ROLE_HOME: Record<Role, string> = {
  family: '/family/dashboard',
  nurse: '/nurse/visits',
  admin: '/admin/dashboard',
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [initialising, setInitialising] = useState(true)

  // On startup: read the stored token, then confirm it with /auth/me.
  useEffect(() => {
    let active = true
    async function restore() {
      if (!getToken()) {
        setInitialising(false)
        return
      }
      try {
        const me = await authApi.me()
        if (active) setUser(me)
      } catch {
        clearToken()
      } finally {
        if (active) setInitialising(false)
      }
    }
    void restore()
    return () => {
      active = false
    }
  }, [])

  // A rejected token anywhere in the app drops the session.
  useEffect(() => onUnauthorized(() => setUser(null)), [])

  const login = useCallback(async (email: string, password: string) => {
    const response = await authApi.login(email, password)
    setToken(response.access_token)
    setUser(response.user)
    return response.user
  }, [])

  const logout = useCallback(() => {
    clearToken()
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, initialising, login, logout }),
    [user, initialising, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside an AuthProvider')
  return context
}
