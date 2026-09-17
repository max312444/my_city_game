import { defineStore } from 'pinia'

const DISPLAY_SECONDS = 6

export const useRandomEventStore = defineStore('randomEvent', {
  state: () => ({
    current: null,
    timerId: null,
  }),
  actions: {
    show(event) {
      if (this.timerId) clearTimeout(this.timerId)
      this.current = event
      this.timerId = setTimeout(() => {
        this.current = null
        this.timerId = null
      }, DISPLAY_SECONDS * 1000)
    },
  },
})
