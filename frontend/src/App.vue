<script setup>
import { ref, computed, watch } from 'vue'
import ClockPanel from './components/ClockPanel.vue'
import TopHud from './components/TopHud.vue'
import GameMenu from './components/GameMenu.vue'
import AdviceBanner from './components/AdviceBanner.vue'
import LoginScreen from './components/LoginScreen.vue'
import NationNamePrompt from './components/NationNamePrompt.vue'
import EventToast from './components/EventToast.vue'
import GreatPersonToast from './components/GreatPersonToast.vue'
import LeftDrawer from './components/LeftDrawer.vue'
import MapCanvas from './components/MapCanvas.vue'
import { useSessionStore } from './stores/session'
import { useNationStore } from './stores/nation'

const sessionStore = useSessionStore()
const nationStore = useNationStore()

const nationLoaded = ref(false)

async function loadNation() {
  nationLoaded.value = false
  await nationStore.fetchInitial()
  nationLoaded.value = true
}

watch(
  () => sessionStore.sessionId,
  (id) => {
    if (id) loadNation()
  },
  { immediate: true },
)

const needsName = computed(
  () => nationLoaded.value && nationStore.nation.name === sessionStore.sessionId,
)
</script>

<template>
  <div class="app">
    <LoginScreen v-if="!sessionStore.sessionId" />
    <NationNamePrompt v-else-if="needsName" @named="nationLoaded = true" />
    <template v-else-if="nationLoaded">
      <MapCanvas />
      <TopHud />
      <div class="right-column">
        <ClockPanel />
        <GameMenu />
      </div>
      <LeftDrawer />
      <AdviceBanner />
      <EventToast />
      <GreatPersonToast />
    </template>
  </div>
</template>

<style scoped>
.app {
  width: 100vw;
  height: 100vh;
  background: var(--bg-app);
}
.right-column {
  position: fixed;
  top: 16px;
  right: 16px;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 12px;
  max-height: calc(100vh - 32px);
  overflow-y: auto;
}
.right-column > * {
  min-width: 190px;
}
</style>
