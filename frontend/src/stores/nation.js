import { defineStore } from 'pinia'
import { useSessionStore } from './session'

const API_BASE = 'http://localhost:8000'

export const useNationStore = defineStore('nation', {
  state: () => ({
    nation: {
      name: '',
      economy: 0,
      stability: 0,
      military: 0,
      education: 0,
      monthly_income: 0,
      monthly_expenses: 0,
      monthly_net: 0,
      treasury: 0,
      is_bankrupt: false,
      population: 0,
      land_capacity: 0,
      population_density: 0,
      satisfaction: 0,
      food_production: 0,
      food_consumption: 0,
      food_net: 0,
      food_stock: 0,
      is_famine: false,
    },
  }),
  actions: {
    async fetchInitial() {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/nation`)
      this.nation = await res.json()
    },
    applyUpdate(nation) {
      this.nation = nation
    },
  },
})
