import { defineStore } from 'pinia'
import { useSessionStore } from './session'
import { useNationStore } from './nation'

const API_BASE = 'http://localhost:8000'

export const useDiplomacyStore = defineStore('diplomacy', {
  state: () => ({
    rivals: [],
    worldRelationships: [],
    error: '',
    lastReports: [],
    reportsTimerId: null,
    pendingPeaceOffer: null,
  }),
  actions: {
    async fetchPeaceOffer() {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/diplomacy/peace-offer`)
      const data = await res.json()
      this.pendingPeaceOffer = data.offer
    },
    setPeaceOffer(offer) {
      this.pendingPeaceOffer = offer
    },
    async respondPeaceOffer(accept) {
      const offer = this.pendingPeaceOffer
      if (!offer) return
      const sessionId = useSessionStore().sessionId
      this.pendingPeaceOffer = null
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/diplomacy/peace-offer/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rival_id: offer.rival_id, accept }),
      })
      const data = await res.json()
      if (data.rivals) this.rivals = data.rivals
    },
    async fetchRivals() {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/diplomacy`)
      const data = await res.json()
      this.rivals = data.rivals
    },
    async fetchWorldRelationships() {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/diplomacy/world`)
      const data = await res.json()
      this.worldRelationships = data.relationships
    },
    rivalName(rivalId) {
      return this.rivals.find((r) => r.rival_id === rivalId)?.name || rivalId
    },
    updateRivals(rivals) {
      // Only the GET /diplomacy fetch computes siege_target_name (it reads the
      // session's in-memory siege_targets) — every other broadcast (monthly drift,
      // declare-war, etc.) returns plain rival dicts without it. Preserve whatever
      // we already knew locally instead of letting it flicker to blank on every
      // month's rivals_updated event; a fresh fetchRivals() (see the war_report
      // handler in clock.js) is what actually clears it once a siege is resolved.
      this.rivals = rivals.map((incoming) => {
        const existing = this.rivals.find((r) => r.rival_id === incoming.rival_id)
        return {
          ...incoming,
          siege_target_name: incoming.siege_target_name ?? existing?.siege_target_name ?? null,
        }
      })
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
    async attackCity(x, y) {
      const sessionId = useSessionStore().sessionId
      this.error = ''
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/diplomacy/attack-city`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x, y }),
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || '공격에 실패했습니다')
      }
      this.rivals = data.rivals.map((r) =>
        r.rival_id === data.rival_id ? { ...r, siege_target_name: data.city_name } : r,
      )
      return data
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
