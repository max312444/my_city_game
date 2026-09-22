import { defineStore } from 'pinia'
import { useSessionStore } from './session'

const API_BASE = 'http://localhost:8000'

export const useGameLogStore = defineStore('gameLog', {
  state: () => ({ entries: [] }),
  actions: {
    async fetchLog() {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/log`)
      const data = await res.json()
      this.entries = data.entries
    },
  },
})
