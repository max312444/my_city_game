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
  <div class="clock-panel panel">
    <div v-if="!clock.connected" class="reconnecting">● 재연결 중...</div>
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
  padding: 12px 16px;
  text-align: right;
}
.reconnecting {
  font-size: 11px;
  color: var(--text-negative);
  margin-bottom: 4px;
  animation: pulse 1.2s ease-in-out infinite;
}
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}
.date-text {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: 700;
  color: var(--accent-strong);
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
  border: 1px solid var(--panel-border-soft);
  background: rgba(0, 0, 0, 0.25);
  color: var(--text);
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  font-family: var(--font-body);
}
button:hover {
  border-color: var(--accent);
}
button.active {
  background: var(--accent-dim);
  border-color: var(--accent);
  color: var(--accent-strong);
}
</style>
