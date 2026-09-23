<script setup>
import { computed, ref } from 'vue'
import DiplomacyPanel from './DiplomacyPanel.vue'
import { useAdviceStore } from '../stores/advice'

const adviceStore = useAdviceStore()
const open = ref(false)

// Same reasoning as PeaceOfferPopup.vue — the advice banner spans the full width at
// the very bottom, so this button/panel shifts up out of its way while one is showing.
const bottomOffset = computed(() => (adviceStore.currentAdvice ? '110px' : '16px'))
</script>

<template>
  <button class="dip-tab panel" :style="{ bottom: bottomOffset }" @click="open = !open">
    {{ open ? '▼' : '▲' }} 전쟁 · 외교
  </button>
  <div class="dip-drawer-panel" :class="{ open }" :style="{ bottom: `calc(${bottomOffset} + 50px)` }">
    <DiplomacyPanel />
  </div>
</template>

<style scoped>
.dip-tab {
  position: fixed;
  left: 16px;
  padding: 10px 14px;
  cursor: pointer;
  font-size: 13px;
  font-weight: bold;
  font-family: var(--font-heading);
  color: var(--text);
  z-index: 21;
  transition: bottom 0.2s ease;
}
.dip-tab:hover {
  border-color: var(--accent);
  color: var(--accent-strong);
}
.dip-drawer-panel {
  position: fixed;
  left: 16px;
  width: 252px;
  max-height: 65vh;
  overflow-y: auto;
  opacity: 0;
  transform: translateY(12px);
  pointer-events: none;
  transition:
    opacity 0.2s ease,
    transform 0.2s ease,
    bottom 0.2s ease;
  z-index: 20;
}
.dip-drawer-panel.open {
  opacity: 1;
  transform: translateY(0);
  pointer-events: auto;
}
</style>
