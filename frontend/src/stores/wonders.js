import { defineStore } from 'pinia'
import { useSessionStore } from './session'
import { useNationStore } from './nation'

const API_BASE = 'http://localhost:8000'

export const useWonderStore = defineStore('wonders', {
  state: () => ({
    wonders: [],
    claims: {}, // { wonder_id: "player" | rival_id }
    currentWonder: null,
    currentWonderMonthsLeft: 0,
    error: '',
    lastEvent: null,
    eventTimerId: null,
  }),
  actions: {
    async fetchState() {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/wonders`)
      const data = await res.json()
      this.wonders = data.wonders
      this.claims = data.claims
      this.currentWonder = data.current_wonder
      this.currentWonderMonthsLeft = data.current_wonder_months_left
    },
    async start(wonderId) {
      const sessionId = useSessionStore().sessionId
      this.error = ''
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/wonders/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wonder_id: wonderId }),
      })
      const data = await res.json()
      if (!res.ok) {
        this.error = data.detail || '건설 시작에 실패했습니다'
        return
      }
      this.currentWonder = data.current_wonder
      this.currentWonderMonthsLeft = data.duration
      useNationStore().applyUpdate(data.nation)
    },
    onWonderCompleted(event) {
      const builder = event.rival_id || 'player'
      this.claims = { ...this.claims, [event.wonder_id]: builder }
      if (this.currentWonder === event.wonder_id) {
        this.currentWonder = null
        this.currentWonderMonthsLeft = 0
      }
      if (event.message) {
        this.lastEvent = event.message
        if (this.eventTimerId) clearTimeout(this.eventTimerId)
        this.eventTimerId = setTimeout(() => {
          this.lastEvent = null
          this.eventTimerId = null
        }, 7000)
      }
    },
  },
})
