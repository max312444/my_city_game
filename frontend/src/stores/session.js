import { defineStore } from 'pinia'

const STORAGE_KEY = 'regnum_session_id'

function readStoredSessionId() {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null // private browsing / storage disabled — fall back to logged-out state
  }
}

export const useSessionStore = defineStore('session', {
  state: () => ({
    sessionId: readStoredSessionId(),
  }),
  actions: {
    setSessionId(id) {
      this.sessionId = id
      try {
        if (id) localStorage.setItem(STORAGE_KEY, id)
        else localStorage.removeItem(STORAGE_KEY)
      } catch {
        // ignore — session just won't survive a refresh in this browser
      }
    },
  },
})
