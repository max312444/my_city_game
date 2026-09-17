<script setup>
import { useNationStore } from '../stores/nation'

const nationStore = useNationStore()

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
  <div class="top-hud">
    <div class="nation-name">{{ nationStore.nation.name }}</div>
    <div class="divider"></div>
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
</template>

<style scoped>
.top-hud {
  position: fixed;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 20px;
  background: rgba(0, 0, 0, 0.65);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 999px;
  color: white;
  font-family: sans-serif;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.4);
  z-index: 15;
}
.nation-name {
  font-weight: bold;
  font-size: 14px;
  color: #ffd166;
  white-space: nowrap;
}
.divider {
  width: 1px;
  height: 18px;
  background: rgba(255, 255, 255, 0.2);
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
  color: #ff6b6b;
}
</style>
