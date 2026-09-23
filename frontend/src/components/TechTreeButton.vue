<script setup>
import { ref } from 'vue'
import TechTreeOverlay from './TechTreeOverlay.vue'

// Tech decisions always happen in the full graph now — no separate compact list
// panel anymore (that used to live in TechPanel.vue, now retired). One click, one
// destination.
const open = ref(false)
</script>

<template>
  <button class="tech-btn panel" @click="open = true">🌳 테크트리</button>
  <TechTreeOverlay v-if="open" @close="open = false" />
</template>

<style scoped>
.tech-btn {
  position: fixed;
  top: 16px;
  left: 16px;
  padding: 10px 14px;
  cursor: pointer;
  font-size: 13px;
  font-weight: bold;
  font-family: var(--font-heading);
  color: var(--text);
  z-index: 15;
}
.tech-btn:hover {
  border-color: var(--accent);
  color: var(--accent-strong);
}
</style>
