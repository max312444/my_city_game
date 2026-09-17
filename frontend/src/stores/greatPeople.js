import { defineStore } from 'pinia'
import { useSessionStore } from './session'

const API_BASE = 'http://localhost:8000'
const DISPLAY_SECONDS = 7

export const useGreatPeopleStore = defineStore('greatPeople', {
  state: () => ({
    history: [],
    current: null,
    timerId: null,
  }),
  actions: {
    async fetchHistory() {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/great-people`)
      const data = await res.json()
      this.history = data.history
    },
    onAppeared(person, currentDate) {
      const entry = { ...person, year: currentDate.year, month: currentDate.month }
      this.history.push(entry)
      if (this.timerId) clearTimeout(this.timerId)
      this.current = entry
      this.timerId = setTimeout(() => {
        this.current = null
        this.timerId = null
      }, DISPLAY_SECONDS * 1000)
    },
  },
})
