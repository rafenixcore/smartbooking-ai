import { create } from 'zustand'
import type { PlatformAdmin } from '@/types/platform'
import { platformAPI } from '@/services/api'

interface PlatformAuthState {
  admin: PlatformAdmin | null
  ready: boolean
  busy: boolean
  login: (email: string, password: string) => Promise<void>
  initialize: () => Promise<void>
  logout: () => Promise<void>
}

export const usePlatformAuthStore = create<PlatformAuthState>((set) => ({
  admin: null,
  ready: false,
  busy: false,

  login: async (email, password) => {
    set({ busy: true })
    try {
      const result = await platformAPI.login(email, password)
      localStorage.setItem('platform_access_token', result.access_token)
      localStorage.setItem('platform_refresh_token', result.refresh)
      set({ admin: result.admin, ready: true })
    } finally {
      set({ busy: false })
    }
  },

  initialize: async () => {
    if (!localStorage.getItem('platform_access_token') && !localStorage.getItem('platform_refresh_token')) {
      set({ admin: null, ready: true })
      return
    }
    try {
      const admin = await platformAPI.me()
      set({ admin, ready: true })
    } catch {
      set({ admin: null, ready: true })
    }
  },

  logout: async () => {
    try {
      await platformAPI.logout()
    } finally {
      set({ admin: null, ready: true })
    }
  },
}))
