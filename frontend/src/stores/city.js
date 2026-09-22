import { defineStore } from 'pinia'
import { useSessionStore } from './session'
import { useNationStore } from './nation'

const API_BASE = 'http://localhost:8000'
const CITY_BASE_COST = 2000
const CITY_COST_GROWTH = 1000

export const useCityStore = defineStore('city', {
  state: () => ({ cities: [] }),
  actions: {
    async fetchCities() {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/cities`)
      const data = await res.json()
      this.cities = data.cities
    },
    updateCities(cities) {
      this.cities = cities
    },
    estimatedCost() {
      return CITY_BASE_COST + CITY_COST_GROWTH * this.cities.length
    },
    async found(x, y, name) {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/cities`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x, y, name }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '도시 건설에 실패했습니다')
      this.cities = data.cities
      useNationStore().applyUpdate(data.nation)
      return data
    },
  },
})
