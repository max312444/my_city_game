import { defineStore } from 'pinia'
import { useNationStore } from './nation'
import { useAdviceStore } from './advice'
import { useSessionStore } from './session'

const API_BASE = 'http://localhost:8000'

export const useClockStore = defineStore('clock', {
  state: () => ({
    currentDate: { year: 1, month: 1 },
    speed: 'normal',
    socket: null,
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
      this.socket = new WebSocket(`ws://localhost:8000/ws/${sessionId}`)
      this.socket.onmessage = (event) => {
        const message = JSON.parse(event.data)
        if (message.event_type === 'month_advanced') {
          this.currentDate = message.payload.current_date
        } else if (message.event_type === 'nation_updated') {
          useNationStore().applyUpdate(message.payload.nation)
        } else if (message.event_type === 'advice_available') {
          useAdviceStore().setAdvice(message.payload.advice)
        }
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
