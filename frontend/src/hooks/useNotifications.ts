import { useState, useCallback } from 'react'
import { api } from '../api/client'
import type { AppNotification } from '../types'
import { useFetch } from './useFetch'

export function useNotifications(isSignedIn: boolean) {
  const [panelOpen, setPanelOpen] = useState(false)

  const { data: countData, refresh: refreshCount } = useFetch<{ unread_count: number }>(
    isSignedIn ? () => api.getUnreadCount() : null,
    [isSignedIn],
    { pollMs: 10_000, pollWhen: () => isSignedIn }
  )

  const { data: listData, loading: listLoading, refresh: refreshList } = useFetch<{
    notifications: AppNotification[]
    unread_count: number
  }>(
    isSignedIn && panelOpen ? () => api.listNotifications(10) : null,
    [isSignedIn, panelOpen]
  )

  const unreadCount = countData?.unread_count ?? 0
  const notifications = listData?.notifications ?? []

  const openPanel = useCallback(() => setPanelOpen(true), [])
  const closePanel = useCallback(() => setPanelOpen(false), [])

  const markRead = useCallback(
    async (notificationId: string) => {
      try {
        await api.markNotificationRead(notificationId)
        refreshList()
        refreshCount()
      } catch (e) {
        console.error('Failed to mark notification read:', e)
      }
    },
    [refreshList, refreshCount]
  )

  const markAllRead = useCallback(async () => {
    try {
      await api.markAllNotificationsRead()
      refreshList()
      refreshCount()
    } catch (e) {
      console.error('Failed to mark all notifications read:', e)
    }
  }, [refreshList, refreshCount])

  return {
    unreadCount,
    notifications,
    listLoading,
    panelOpen,
    openPanel,
    closePanel,
    markRead,
    markAllRead,
  }
}
