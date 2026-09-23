<script setup>
import { ref, computed, watch, nextTick } from 'vue'
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
import PeaceOfferPopup from './components/PeaceOfferPopup.vue'
import VictoryScreen from './components/VictoryScreen.vue'
import Guidebook from './components/Guidebook.vue'
import TechTreeButton from './components/TechTreeButton.vue'
import DiplomacyDrawer from './components/DiplomacyDrawer.vue'
import { useSessionStore } from './stores/session'
import { useNationStore } from './stores/nation'
import { useDiplomacyStore } from './stores/diplomacy'

const sessionStore = useSessionStore()
const nationStore = useNationStore()
const diplomacyStore = useDiplomacyStore()

const nationLoaded = ref(false)
const guidebookRef = ref(null)

async function loadNation() {
  nationLoaded.value = false
  await nationStore.fetchInitial()
  nationLoaded.value = true
}

async function onNationNamed() {
  nationLoaded.value = true
  // <Guidebook> only exists once nationLoaded flips the v-else-if branch, so its ref
  // isn't mounted yet in this same synchronous tick — wait for the DOM update first.
  await nextTick()
  // Only ever fires right after a brand-new game's naming prompt — "이어하기" skips
  // straight past it, so returning players never get this popped on them again.
  if (guidebookRef.value) guidebookRef.value.open = true
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

const gameWon = computed(
  () => diplomacyStore.rivals.length > 0 && diplomacyStore.rivals.every((r) => r.relationship === 'defeated'),
)
</script>

<template>
  <div class="app">
    <LoginScreen v-if="!sessionStore.sessionId" />
    <NationNamePrompt v-else-if="needsName" @named="onNationNamed" />
    <template v-else-if="nationLoaded">
      <MapCanvas />
      <TopHud />
      <div class="right-column">
        <ClockPanel />
        <GameMenu />
        <Guidebook ref="guidebookRef" />
      </div>
      <TechTreeButton />
      <LeftDrawer />
      <DiplomacyDrawer />
      <AdviceBanner />
      <EventToast />
      <GreatPersonToast />
      <PeaceOfferPopup />
      <VictoryScreen v-if="gameWon" />
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
