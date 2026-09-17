import { defineStore } from 'pinia'
import { useSessionStore } from './session'
import { useNationStore } from './nation'

const API_BASE = 'http://localhost:8000'

export const useTechStore = defineStore('tech', {
  state: () => ({
    tree: [],
    researched: [],
    currentResearch: null,
    currentResearchMonthsLeft: 0,
    error: '',
  }),
  actions: {
    async fetchTree() {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/tech`)
      const data = await res.json()
      this.tree = data.tree
      this.researched = data.researched
      this.currentResearch = data.current_research
      this.currentResearchMonthsLeft = data.current_research_months_left
    },
    async research(techId) {
      const sessionId = useSessionStore().sessionId
      this.error = ''
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/tech/research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tech_id: techId }),
      })
      const data = await res.json()
      if (!res.ok) {
        this.error = data.detail || '연구에 실패했습니다'
        return
      }
      this.researched = data.researched
      this.currentResearch = data.current_research
      this.currentResearchMonthsLeft = data.current_research_months_left
      useNationStore().applyUpdate(data.nation)
    },
    onTechCompleted(techId) {
      if (!this.researched.includes(techId)) {
        this.researched.push(techId)
      }
      if (this.currentResearch === techId) {
        this.currentResearch = null
        this.currentResearchMonthsLeft = 0
      }
    },
  },
})
