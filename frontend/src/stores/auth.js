import { defineStore } from 'pinia'
import { useSessionStore } from './session'

const API_BASE = 'http://localhost:8000'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    displayName: null,
  }),
  actions: {
    async checkUsername(username) {
      const res = await fetch(`${API_BASE}/api/auth/check-username?username=${encodeURIComponent(username)}`)
      const data = await res.json()
      return data.available
    },
    async signup(username, password, displayName) {
      const res = await fetch(`${API_BASE}/api/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, display_name: displayName }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '회원가입에 실패했습니다')
      this.displayName = data.display_name
      useSessionStore().setSessionId(data.username)
    },
    async login(username, password) {
      // Unlike signup, login does NOT set the session id right away — an existing
      // account may have a save worth keeping, so LoginScreen.vue asks
      // "이어하기 / 새로 만들기" first and only enters the game once the player picks.
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '로그인에 실패했습니다')
      this.displayName = data.display_name
      return data.username
    },
  },
})
