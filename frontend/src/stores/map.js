import { defineStore } from 'pinia'
import { useSessionStore } from './session'

const API_BASE = 'http://localhost:8000'

export const useMapStore = defineStore('map', {
  state: () => ({
    width: 0,
    height: 0,
    tiles: [],
    capital: null,
    rivalCapitals: [],
  }),
  actions: {
    async fetchMap() {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/map`)
      const data = await res.json()
      this.width = data.width
      this.height = data.height
      this.tiles = data.tiles
      this.capital = data.capital
      this.rivalCapitals = data.rival_capitals || []
    },
  },
})
