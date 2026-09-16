<script setup>
import ClockPanel from './components/ClockPanel.vue'
import NationPanel from './components/NationPanel.vue'
import AdviceBanner from './components/AdviceBanner.vue'
import StartScreen from './components/StartScreen.vue'
import { useSessionStore } from './stores/session'

const sessionStore = useSessionStore()
</script>

<template>
  <div class="app">
    <StartScreen v-if="!sessionStore.sessionId" />
    <template v-else>
      <ClockPanel />
      <NationPanel />
      <AdviceBanner />
    </template>
  </div>
</template>

<style scoped>
.app {
  width: 100vw;
  height: 100vh;
  background: #1a1a1a;
}
</style>
