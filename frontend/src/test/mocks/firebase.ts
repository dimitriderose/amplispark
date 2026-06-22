import { vi } from 'vitest'

export const auth = { currentUser: null }
export const signInWithGoogle = vi.fn().mockResolvedValue({ uid: 'test-uid', displayName: 'Test User', email: 'test@test.com', photoURL: null })
export const signOutUser = vi.fn().mockResolvedValue(undefined)
export const onAuthStateChanged = vi.fn()
export const getIdToken = vi.fn().mockResolvedValue('fake-token')
export const getFreshIdToken = vi.fn().mockResolvedValue('fake-token')
export const getUid = vi.fn().mockReturnValue('test-uid')
export const getCurrentUser = vi.fn().mockReturnValue({ displayName: 'Test User', photoURL: null, email: 'test@test.com' })
