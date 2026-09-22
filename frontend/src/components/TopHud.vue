<script setup>
import { ref } from 'vue'
import { useNationStore } from '../stores/nation'

const nationStore = useNationStore()
const open = ref(false)

const items = [
  { icon: '👥', key: 'population', title: '인구' },
  { icon: '🌾', key: 'food_stock', title: '식량 비축량' },
  { icon: '💰', key: 'treasury', title: '보유 금액' },
  { icon: '📈', key: 'economy', title: '경제력' },
  { icon: '⚖️', key: 'stability', title: '안정도' },
  { icon: '⚔️', key: 'military', title: '군사력' },
  { icon: '📚', key: 'education', title: '교육' },
]
</script>

<template>
  <div class="hud-wrap">
    <button class="hud-tab panel" @click="open = !open">
      <span class="nation-name">{{ nationStore.nation.name }}</span>
      <span class="chevron">{{ open ? '▲' : '▼' }}</span>
    </button>
    <div class="hud-stats panel" :class="{ open }">
      <div v-for="item in items" :key="item.key" class="stat" :title="item.title">
        <span class="icon">{{ item.icon }}</span>
        <span
          class="value"
          :class="{
            negative:
              (item.key === 'treasury' && nationStore.nation.is_bankrupt) ||
              (item.key === 'food_stock' && nationStore.nation.is_famine),
          }"
        >
          {{ nationStore.nation[item.key] }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hud-wrap {
  position: fixed;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  z-index: 15;
}
.hud-tab {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 20px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 13px;
}
.hud-tab:hover {
  border-color: var(--accent);
}
.nation-name {
  font-family: var(--font-heading);
  font-weight: 600;
  font-size: 14px;
  color: var(--accent-strong);
  white-space: nowrap;
}
.chevron {
  color: var(--text-faint);
  font-size: 10px;
}
.hud-stats {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 0;
  padding: 0 20px;
  max-height: 0;
  overflow: hidden;
  opacity: 0;
  border-radius: 10px;
  transition:
    max-height 0.22s ease,
    opacity 0.18s ease,
    padding 0.22s ease,
    margin-top 0.22s ease;
}
.hud-stats.open {
  margin-top: 8px;
  padding: 10px 20px;
  max-height: 60px;
  opacity: 1;
}
.stat {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  white-space: nowrap;
}
.value {
  font-weight: bold;
}
.value.negative {
  color: var(--text-negative);
}
</style>
