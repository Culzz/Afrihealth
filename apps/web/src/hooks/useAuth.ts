import { useEffect, useState, useCallback } from 'react'
import { api, Me } from '../api/client'

export function useAuth() {
  const [me, setMe] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(() => {
    setLoading(true)
    api.get<Me>('/auth/me')
      .then(setMe)
      .catch(() => setMe(null))            // 401 → anonymous; normal state
      .finally(() => setLoading(false))
  }, [])

  useEffect(refresh, [refresh])

  const login = async (email: string, password: string) => {
    setError(null)
    try {
      const m = await api.post<Me>('/auth/login', { email, password })
      setMe(m)
      return true
    } catch (e) {
      setError(String(e).replace(/^Error: /, ''))
      return false
    }
  }

  const register = async (org_name: string, display_name: string,
                          email: string, password: string) => {
    setError(null)
    try {
      const m = await api.post<Me>('/auth/register', {
        org_name, display_name, email, password })
      setMe(m)
      return true
    } catch (e) {
      setError(String(e).replace(/^Error: /, ''))
      return false
    }
  }

  const logout = async () => {
    await api.post('/auth/logout', {}).catch(() => {})
    setMe(null)
  }

  return { me, loading, error, login, register, logout, refresh }
}
