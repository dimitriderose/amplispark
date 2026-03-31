import { useState, useEffect, useCallback, useRef } from 'react'
import {
  auth,
  signInWithGoogle,
  signOutUser,
  onAuthStateChanged,
  type User,
} from '../api/firebase'

export interface AuthUser {
  displayName: string | null
  photoURL: string | null
  email: string | null
}

export function useAuth() {
  const [uid, setUid] = useState<string | null>(null)
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  const isMounted = useRef(true)

  useEffect(() => {
    isMounted.current = true
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser: User | null) => {
      if (!isMounted.current) return
      if (firebaseUser) {
        setUid(firebaseUser.uid)
        setUser({
          displayName: firebaseUser.displayName,
          photoURL: firebaseUser.photoURL,
          email: firebaseUser.email,
        })
      } else {
        setUid(null)
        setUser(null)
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
  }, [])

  const isSignedIn = uid !== null

  return { uid, user, loading, isSignedIn, signIn, signOut }
}
