<script setup>
import { useRandomEventStore } from '../stores/randomEvent'

const eventStore = useRandomEventStore()
</script>

<template>
  <div
    v-if="eventStore.current"
    class="event-toast"
    :class="eventStore.current.positive ? 'positive' : 'negative'"
  >
    <div class="icon">{{ eventStore.current.positive ? '✨' : '⚠' }}</div>
    <div class="text">
      <div class="title">{{ eventStore.current.name }}</div>
      <div class="description">{{ eventStore.current.description }}</div>
    </div>
  </div>
</template>

<style scoped>
.event-toast {
  position: fixed;
  top: 76px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 18px;
  border-radius: 8px;
  color: white;
  font-family: sans-serif;
  max-width: 420px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
  z-index: 20;
}
.event-toast.negative {
  background: rgba(120, 30, 30, 0.92);
  border: 1px solid #ff6b6b;
}
.event-toast.positive {
  background: rgba(30, 90, 60, 0.92);
  border: 1px solid #4ade80;
}
.icon {
  font-size: 20px;
  line-height: 1.2;
}
.title {
  font-weight: bold;
  font-size: 14px;
  margin-bottom: 2px;
}
.description {
  font-size: 12px;
  color: #eee;
}
</style>
