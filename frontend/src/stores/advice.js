import { defineStore } from 'pinia'
import { useSessionStore } from './session'

const API_BASE = 'http://localhost:8000'

export const useAdviceStore = defineStore('advice', {
  state: () => ({
    currentAdvice: null,
  }),
  actions: {
    async fetchPending() {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/advice/pending`)
      const data = await res.json()
      this.currentAdvice = data.advice
    },
    setAdvice(advice) {
      this.currentAdvice = advice
    },
    async choose(choiceId) {
      if (!this.currentAdvice) return
      const sessionId = useSessionStore().sessionId
      const adviceId = this.currentAdvice.id
      await fetch(`${API_BASE}/api/session/${sessionId}/advice/choose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ advice_id: adviceId, choice_id: choiceId }),
      })
      this.currentAdvice = null
    },
    async dismiss() {
      if (!this.currentAdvice) return
      const sessionId = useSessionStore().sessionId
      const adviceId = this.currentAdvice.id
      this.currentAdvice = null
      await fetch(`${API_BASE}/api/session/${sessionId}/advice/dismiss`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ advice_id: adviceId }),
      })
    },
  },
})
