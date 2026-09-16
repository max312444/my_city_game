import { defineStore } from 'pinia'

export const useSessionStore = defineStore('session', {
  state: () => ({
    sessionId: null,
  }),
  actions: {
    setSessionId(id) {
      this.sessionId = id
    },
  },
})
