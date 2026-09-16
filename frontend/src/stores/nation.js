import { defineStore } from 'pinia'
import { useSessionStore } from './session'

const API_BASE = 'http://localhost:8000'

export const useNationStore = defineStore('nation', {
  state: () => ({
    nation: {
      name: '',
      economy: 0,
      stability: 0,
      military: 0,
      education: 0,
      monthly_income: 0,
      treasury: 0,
    },
  }),
  actions: {
    async fetchInitial() {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/nation`)
      this.nation = await res.json()
    },
    applyUpdate(nation) {
      this.nation = nation
    },
  },
})
