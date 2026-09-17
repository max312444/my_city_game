<script setup>
import { onMounted, computed } from 'vue'
import { useClockStore } from '../stores/clock'

const clock = useClockStore()

onMounted(async () => {
  await clock.fetchInitial()
  clock.connect()
})

const dateText = computed(() => {
  const d = clock.currentDate
  return `${d.year}년 ${d.month}월`
})

const speeds = [
  { value: 'paused', label: '일시정지' },
  { value: 'normal', label: '1x' },
  { value: 'fast', label: '2x' },
  { value: 'fastest', label: '4x' },
]
</script>

<template>
  <div class="clock-panel">
    <div class="date-text">{{ dateText }}</div>
    <div class="speed-buttons">
      <button
        v-for="s in speeds"
        :key="s.value"
        :class="{ active: clock.speed === s.value }"
        @click="clock.setSpeed(s.value)"
      >
        {{ s.label }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.clock-panel {
  background: rgba(0, 0, 0, 0.6);
  color: white;
  padding: 12px 16px;
  border-radius: 8px;
  font-family: sans-serif;
  text-align: right;
}
.date-text {
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 8px;
}
.speed-buttons {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}
button {
  padding: 4px 10px;
  border-radius: 4px;
  border: 1px solid #888;
  background: #333;
  color: white;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
}
button.active {
  background: #4a90d9;
  border-color: #4a90d9;
}
</style>
