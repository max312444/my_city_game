import { defineStore } from 'pinia'
import { useSessionStore } from './session'
import { useNationStore } from './nation'

const API_BASE = 'http://localhost:8000'

export const useDiplomacyStore = defineStore('diplomacy', {
  state: () => ({
    rivals: [],
    error: '',
    lastReports: [],
    reportsTimerId: null,
  }),
  actions: {
    async fetchRivals() {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/diplomacy`)
      const data = await res.json()
      this.rivals = data.rivals
    },
    updateRivals(rivals) {
      this.rivals = rivals
    },
    async declareWar(rivalId) {
      const sessionId = useSessionStore().sessionId
      this.error = ''
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/diplomacy/declare-war`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rival_id: rivalId }),
      })
      const data = await res.json()
      if (!res.ok) {
        this.error = data.detail || '실패했습니다'
        return
      }
      this.rivals = data.rivals
      useNationStore().applyUpdate(data.nation)
    },
    async proposePeace(rivalId) {
      const sessionId = useSessionStore().sessionId
      this.error = ''
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/diplomacy/propose-peace`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rival_id: rivalId }),
      })
      const data = await res.json()
      if (!res.ok) {
        this.error = data.detail || '실패했습니다'
        return null
      }
      this.rivals = data.rivals
      return data.accepted
    },
    showReports(reports) {
      this.lastReports = reports
      if (this.reportsTimerId) clearTimeout(this.reportsTimerId)
      this.reportsTimerId = setTimeout(() => {
        this.lastReports = []
        this.reportsTimerId = null
      }, 6000)
    },
  },
})
