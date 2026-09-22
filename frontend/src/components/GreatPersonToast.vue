<script setup>
import { useGreatPeopleStore } from '../stores/greatPeople'

const greatPeopleStore = useGreatPeopleStore()
</script>

<template>
  <div v-if="greatPeopleStore.current" class="gp-toast">
    <div class="icon">👑</div>
    <div class="text">
      <div class="title">위인 등장 — {{ greatPeopleStore.current.name }} ({{ greatPeopleStore.current.title }})</div>
      <div class="description">{{ greatPeopleStore.current.description }}</div>
    </div>
  </div>
</template>

<style scoped>
.gp-toast {
  position: fixed;
  top: 150px;
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
  background: rgba(52, 38, 14, 0.94);
  border: 1px solid var(--accent-strong);
  box-shadow: var(--panel-shadow);
  z-index: 20;
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
