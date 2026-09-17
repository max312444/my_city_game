<script setup>
import { onMounted, onUnmounted, ref, watch, computed } from 'vue'
import { useAdviceStore } from '../stores/advice'
import { useClockStore } from '../stores/clock'

const adviceStore = useAdviceStore()
const clockStore = useClockStore()

const secondsLeft = ref(0)
const totalSeconds = ref(1)
let intervalId = null

watch(
  () => adviceStore.currentAdvice,
  (advice) => {
    if (advice) {
      secondsLeft.value = advice.seconds_left
      totalSeconds.value = advice.total_seconds || 1
      if (!intervalId) {
        intervalId = setInterval(() => {
          // Purely visual: the server is the source of truth and clears
          // currentAdvice for us once its own (pause-aware) timer hits zero.
          if (clockStore.speed !== 'paused') {
            secondsLeft.value = Math.max(0, secondsLeft.value - 0.5)
          }
        }, 500)
      }
    } else if (intervalId) {
      clearInterval(intervalId)
      intervalId = null
    }
  },
  { immediate: true },
)

onMounted(() => {
  adviceStore.fetchPending()
})

onUnmounted(() => {
  if (intervalId) clearInterval(intervalId)
})

const timeLeft = computed(() => Math.ceil(secondsLeft.value))

const timePercent = computed(() => {
  if (!totalSeconds.value) return 0
  return Math.max(0, Math.min(100, (secondsLeft.value / totalSeconds.value) * 100))
})

function choose(choiceId) {
  adviceStore.choose(choiceId)
}
</script>

<template>
  <div v-if="adviceStore.currentAdvice" class="advice-banner">
    <div class="timer-bar" :style="{ width: timePercent + '%' }"></div>
    <div class="content">
      <div class="text">
        <div class="title">
          {{ adviceStore.currentAdvice.title }}
          <span class="timer">{{ timeLeft }}초{{ clockStore.speed === 'paused' ? ' (일시정지)' : '' }}</span>
        </div>
        <div class="description">{{ adviceStore.currentAdvice.description }}</div>
      </div>
      <div class="choices">
        <button
          v-for="choice in adviceStore.currentAdvice.choices"
          :key="choice.id"
          @click="choose(choice.id)"
        >
          {{ choice.label }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.advice-banner {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(20, 20, 20, 0.92);
  color: white;
  font-family: sans-serif;
  border-top: 1px solid #555;
}
.timer-bar {
  height: 3px;
  background: #4a90d9;
  transition: width 0.2s linear;
}
.content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 20px;
  flex-wrap: wrap;
}
.text {
  flex: 1 1 260px;
  min-width: 0;
}
.title {
  font-weight: bold;
  font-size: 15px;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.timer {
  color: #ffb84a;
  font-size: 13px;
  font-weight: normal;
}
.description {
  font-size: 13px;
  color: #ccc;
}
.choices {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
button {
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #555;
  background: #333;
  color: white;
  cursor: pointer;
  font-size: 13px;
  white-space: nowrap;
}
button:hover {
  background: #4a90d9;
  border-color: #4a90d9;
}
</style>
