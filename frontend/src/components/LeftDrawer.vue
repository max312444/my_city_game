<script setup>
import { ref } from 'vue'
import TechPanel from './TechPanel.vue'
import DiplomacyPanel from './DiplomacyPanel.vue'

const open = ref(false)
</script>

<template>
  <button class="drawer-tab" :class="{ open }" @click="open = !open">
    {{ open ? '◀' : '▶' }} 테크 · 외교
  </button>
  <div class="drawer-panel" :class="{ open }">
    <TechPanel />
    <DiplomacyPanel />
  </div>
</template>

<style scoped>
.drawer-tab {
  position: fixed;
  top: 50%;
  left: 0;
  transform: translateY(-50%);
  writing-mode: vertical-rl;
  text-orientation: mixed;
  padding: 16px 6px;
  border: 1px solid var(--panel-border);
  border-left: none;
  border-radius: 0 8px 8px 0;
  background: var(--panel-bg);
  color: var(--text);
  font-family: var(--font-heading);
  font-size: 13px;
  font-weight: bold;
  cursor: pointer;
  z-index: 21;
  transition: left 0.25s ease;
}
.drawer-tab:hover {
  color: var(--accent-strong);
  border-color: var(--accent);
}
.drawer-tab.open {
  left: 252px;
}
.drawer-panel {
  position: fixed;
  top: 0;
  left: 0;
  height: 100vh;
  width: 252px;
  box-sizing: border-box;
  padding: 16px 16px 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  transform: translateX(-100%);
  transition: transform 0.25s ease;
  z-index: 20;
}
.drawer-panel.open {
  transform: translateX(0);
}
</style>
