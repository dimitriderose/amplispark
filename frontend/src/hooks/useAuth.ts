import { useState, useEffect, useCallback, useRef } from 'react'
import {
  auth,
  signInWithGoogle,
  signOutUser,
  onAuthStateChanged,
  type User,
} from '../api/firebase'
import { api } from '../api/client'

export interface AuthUser {
  displayName: string | null
  photoURL: string | null
  email: string | null
}

type Role = 'beta' | 'user' | 'admin'

interface UsageCounters {
  quickPostsThisMonth: number
  calendarsThisMonth: number
  daysRemaining: number | null
  quickPostsLimit: number | null
  calendarsLimit: number | null
}

export function useAuth() {
  const [uid, setUid] = useState<string | null>(null)
  const [user, setUser] = useState<AuthUser | null>(null)
  const [role, setRole] = useState<Role | null>(null)
  const [betaExpired, setBetaExpired] = useState(false)
  const [usageCounters, setUsageCounters] = useState<UsageCounters | null>(null)
  const [loading, setLoading] = useState(true)
  const [userFetchError, setUserFetchError] = useState(false)

  const isMounted = useRef(true)

  useEffect(() => {
    isMounted.current = true
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser: User | null) => {
      if (!isMounted.current) return
      if (firebaseUser) {
        setUid(firebaseUser.uid)
        setUser({
          displayName: firebaseUser.displayName,
          photoURL: firebaseUser.photoURL,
          email: firebaseUser.email,
        })
        try {
          const userData = await api.getUser()
          if (!isMounted.current) return
          setRole(userData.role)
          setUserFetchError(false)
          setUsageCounters({
            quickPostsThisMonth: userData.quick_posts_this_month,
            calendarsThisMonth: userData.calendars_this_month,
            daysRemaining: userData.days_remaining,
            quickPostsLimit: userData.quick_posts_limit,
            calendarsLimit: userData.calendars_limit,
          })
          if (userData.role === 'beta' && userData.beta_expires_at) {
            setBetaExpired(new Date(userData.beta_expires_at) < new Date())
          } else {
            setBetaExpired(false)
          }
        } catch (err: unknown) {
          if (!isMounted.current) return
          const isNotFound = err instanceof Error && err.message.includes('404')
          if (isNotFound) {
            setRole(null)
            setUserFetchError(false)
          } else {
            setUserFetchError(true)
          }
          setUsageCounters(null)
          setBetaExpired(false)
        }
      } else {
        setUid(null)
        setUser(null)
        setRole(null)
        setBetaExpired(false)
        setUsageCounters(null)
      }
      setLoading(false)
    })
    return () => {
      isMounted.current = false
      unsubscribe()
    }
  }, [])

  const signIn = useCallback(async () => {
    await signInWithGoogle()
  }, [])

  const signOut = useCallback(async () => {
    await signOutUser()
    setUid(null)
    setUser(null)
    setRole(null)
    setBetaExpired(false)
    setUsageCounters(null)
  }, [])

  const isSignedIn = uid !== null

  return { uid, user, role, betaExpired, usageCounters, loading, userFetchError, isSignedIn, signIn, signOut }
}
