import { defineStore } from 'pinia'
import { useSessionStore } from './session'
import { useNationStore } from './nation'

const API_BASE = 'http://localhost:8000'

export const useTradeStore = defineStore('trade', {
  state: () => ({
    routes: [],
    foodStock: 0,
    foodSellRate: 2,
    foodSellMinReserve: 10,
    error: '',
  }),
  actions: {
    async fetchState() {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/trade`)
      const data = await res.json()
      this.routes = data.routes
      this.foodStock = data.food_stock
      this.foodSellRate = data.food_sell_rate
      this.foodSellMinReserve = data.food_sell_min_reserve
    },
    async establish(rivalId) {
      const sessionId = useSessionStore().sessionId
      this.error = ''
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/trade/establish`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rival_id: rivalId }),
      })
      const data = await res.json()
      if (!res.ok) {
        this.error = data.detail || '교역로 개설에 실패했습니다'
        return
      }
      await this.fetchState()
    },
    async close(rivalId) {
      const sessionId = useSessionStore().sessionId
      await fetch(`${API_BASE}/api/session/${sessionId}/trade/close`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rival_id: rivalId }),
      })
      await this.fetchState()
    },
    async sellFood(amount) {
      const sessionId = useSessionStore().sessionId
      this.error = ''
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/trade/sell-food`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount }),
      })
      const data = await res.json()
      if (!res.ok) {
        this.error = data.detail || '판매에 실패했습니다'
        return
      }
      useNationStore().applyUpdate(data.nation)
      this.foodStock = data.nation.food_stock
    },
  },
})
