import { defineStore } from 'pinia'
import { useSessionStore } from './session'
import { useNationStore } from './nation'

const API_BASE = 'http://localhost:8000'

export const useBuildingStore = defineStore('buildings', {
  state: () => ({
    buildings: [],
    built: [],
    researched: [],
    currentBuilding: null,
    currentBuildingMonthsLeft: 0,
    error: '',
  }),
  actions: {
    async fetchState() {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/buildings`)
      const data = await res.json()
      this.buildings = data.buildings
      this.built = data.built
      this.researched = data.researched
      this.currentBuilding = data.current_building
      this.currentBuildingMonthsLeft = data.current_building_months_left
    },
    onBuildingCompleted(buildingId) {
      if (!this.built.includes(buildingId)) this.built.push(buildingId)
      if (this.currentBuilding === buildingId) {
        this.currentBuilding = null
        this.currentBuildingMonthsLeft = 0
      }
    },
    async build(buildingId) {
      const sessionId = useSessionStore().sessionId
      this.error = ''
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/buildings/build`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ building_id: buildingId }),
      })
      const data = await res.json()
      if (!res.ok) {
        this.error = data.detail || '건설에 실패했습니다'
        return
      }
      this.currentBuilding = data.current_building
      this.currentBuildingMonthsLeft = data.current_building_months_left
      useNationStore().applyUpdate(data.nation)
    },
  },
})
