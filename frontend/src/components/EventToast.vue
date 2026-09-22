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
  border-radius: var(--panel-radius);
  color: var(--text);
  font-family: var(--font-body);
  max-width: 420px;
  box-shadow: var(--panel-shadow);
  z-index: 20;
}
.event-toast.negative {
  background: rgba(60, 24, 20, 0.94);
  border: 1px solid var(--text-negative);
}
.event-toast.positive {
  background: rgba(24, 44, 28, 0.94);
  border: 1px solid var(--text-positive);
}
.icon {
  font-size: 20px;
  line-height: 1.2;
}
.title {
  font-family: var(--font-heading);
  font-weight: bold;
  font-size: 14px;
  margin-bottom: 2px;
  color: var(--accent-strong);
}
.description {
  font-size: 12px;
  color: var(--text-dim);
}
</style>
