<script setup>
import { onMounted } from 'vue'
import { useNationStore } from '../stores/nation'

const nationStore = useNationStore()

onMounted(() => {
  nationStore.fetchInitial()
})

const stats = [
  { key: 'economy', label: '경제력' },
  { key: 'stability', label: '안정도' },
  { key: 'military', label: '군사력' },
  { key: 'education', label: '교육' },
]
</script>

<template>
  <div class="nation-panel">
    <div class="nation-name">{{ nationStore.nation.name }}</div>
    <div class="stat-row" v-for="s in stats" :key="s.key">
      <span class="stat-label">{{ s.label }}</span>
      <span class="stat-value">{{ nationStore.nation[s.key] }}</span>
    </div>
    <div class="divider"></div>
    <div class="stat-row">
      <span class="stat-label">월 수입</span>
      <span class="stat-value">{{ nationStore.nation.monthly_income }}</span>
    </div>
    <div class="stat-row">
      <span class="stat-label">보유 금액</span>
      <span class="stat-value">{{ nationStore.nation.treasury }}</span>
    </div>
  </div>
</template>

<style scoped>
.nation-panel {
  position: fixed;
  top: 100px;
  right: 16px;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  padding: 12px 16px;
  border-radius: 8px;
  font-family: sans-serif;
  min-width: 140px;
}
.nation-name {
  font-weight: bold;
  margin-bottom: 8px;
}
.stat-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 14px;
  padding: 2px 0;
}
.stat-label {
  color: #ccc;
}
.stat-value {
  font-weight: bold;
}
.divider {
  border-top: 1px solid #555;
  margin: 6px 0;
}
</style>
