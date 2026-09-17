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
  border-radius: 8px;
  color: white;
  font-family: sans-serif;
  max-width: 420px;
  background: rgba(90, 70, 20, 0.92);
  border: 1px solid #ffd166;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
  z-index: 20;
}
.icon {
  font-size: 20px;
  line-height: 1.2;
}
.title {
  font-weight: bold;
  font-size: 14px;
  margin-bottom: 2px;
  color: #ffd166;
}
.description {
  font-size: 12px;
  color: #f0e6d0;
}
</style>
