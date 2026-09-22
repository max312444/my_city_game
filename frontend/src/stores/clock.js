import { defineStore } from 'pinia'
import { useNationStore } from './nation'
import { useAdviceStore } from './advice'
import { useSessionStore } from './session'
import { useTechStore } from './tech'
import { useRandomEventStore } from './randomEvent'
import { useGreatPeopleStore } from './greatPeople'
import { useDiplomacyStore } from './diplomacy'
import { useTerritoryStore } from './territory'
import { useCityStore } from './city'

const API_BASE = 'http://localhost:8000'

export const useClockStore = defineStore('clock', {
  state: () => ({
    currentDate: { year: 1, month: 1 },
    speed: 'normal',
    socket: null,
    connected: true,
    reconnectAttempts: 0,
  }),
  actions: {
    async fetchInitial() {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/clock`)
      const data = await res.json()
      this.currentDate = data.current_date
      this.speed = data.speed
    },
    connect() {
      const sessionId = useSessionStore().sessionId
      const ws = new WebSocket(`ws://localhost:8000/ws/${sessionId}`)
      this.socket = ws

      ws.onopen = () => {
        this.connected = true
        this.reconnectAttempts = 0
      }
      ws.onclose = () => {
        // If this.socket no longer points at this exact socket, disconnect() already
        // superseded it (intentional logout/reload) — nothing to reconnect.
        if (this.socket !== ws) return
        this.connected = false
        const sid = useSessionStore().sessionId
        if (!sid) return
        const delay = Math.min(1000 * 2 ** this.reconnectAttempts, 15000)
        this.reconnectAttempts += 1
        setTimeout(() => {
          if (useSessionStore().sessionId === sid) this.connect()
        }, delay)
      }
      ws.onmessage = (event) => {
        const message = JSON.parse(event.data)
        if (message.event_type === 'month_advanced') {
          this.currentDate = message.payload.current_date
          const tech = useTechStore()
          if (tech.currentResearch) {
            tech.currentResearchMonthsLeft = Math.max(0, tech.currentResearchMonthsLeft - 1)
          }
        } else if (message.event_type === 'nation_updated') {
          useNationStore().applyUpdate(message.payload.nation)
        } else if (message.event_type === 'advice_available') {
          useAdviceStore().setAdvice(message.payload.advice)
        } else if (message.event_type === 'tech_completed') {
          useTechStore().onTechCompleted(message.payload.tech_id)
        } else if (message.event_type === 'random_event') {
          useRandomEventStore().show(message.payload.event)
        } else if (message.event_type === 'great_person_appeared') {
          useGreatPeopleStore().onAppeared(message.payload.person, message.payload.current_date)
        } else if (message.event_type === 'rivals_updated') {
          useDiplomacyStore().updateRivals(message.payload.rivals)
        } else if (message.event_type === 'war_report') {
          useDiplomacyStore().showReports(message.payload.reports)
          useDiplomacyStore().fetchWorldRelationships()
        } else if (message.event_type === 'territory_updated') {
          useTerritoryStore().updateAll(message.payload.all)
        } else if (message.event_type === 'cities_updated') {
          useCityStore().updateCities(message.payload.cities)
        }
      }
    },
    disconnect() {
      if (this.socket) {
        const ws = this.socket
        this.socket = null
        ws.onclose = null // this is an intentional close — don't let it trigger a reconnect
        ws.close()
      }
    },
    async setSpeed(speed) {
      this.speed = speed
      const sessionId = useSessionStore().sessionId
      await fetch(`${API_BASE}/api/session/${sessionId}/clock/speed`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ speed }),
      })
    },
  },
})
