<script setup>
import { ref } from 'vue'
import BuildingPanel from './BuildingPanel.vue'
import WonderPanel from './WonderPanel.vue'
import TradePanel from './TradePanel.vue'

// One shared sliding panel, three independent tabs — clicking a tab shows its
// content and slides the panel out; clicking the already-open tab collapses it.
// Only ever one tab open at a time (activeTab is a single ref), so the panel
// never has two tabs' content trying to occupy the same 252px column at once.
const TABS = [
  { id: 'building', label: '건물', topPercent: 32 },
  { id: 'wonder', label: '유산', topPercent: 52 },
  { id: 'trade', label: '교역', topPercent: 72 },
]

const activeTab = ref(null) // null | 'building' | 'wonder' | 'trade'

function toggle(id) {
  activeTab.value = activeTab.value === id ? null : id
}
</script>

<template>
  <button
    v-for="tab in TABS"
    :key="tab.id"
    class="drawer-tab"
    :class="{ open: activeTab === tab.id }"
    :style="{ top: tab.topPercent + '%' }"
    @click="toggle(tab.id)"
  >
    {{ activeTab === tab.id ? '◀' : '▶' }} {{ tab.label }}
  </button>
  <div class="drawer-panel" :class="{ open: !!activeTab }">
    <BuildingPanel v-if="activeTab === 'building'" />
    <WonderPanel v-if="activeTab === 'wonder'" />
    <TradePanel v-if="activeTab === 'trade'" />
  </div>
</template>

<style scoped>
.drawer-tab {
  position: fixed;
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
