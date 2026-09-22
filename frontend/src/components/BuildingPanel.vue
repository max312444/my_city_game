<script setup>
import { onMounted } from 'vue'
import { useBuildingStore } from '../stores/buildings'
import { useTechStore } from '../stores/tech'
import { useNationStore } from '../stores/nation'

const buildingStore = useBuildingStore()
const techStore = useTechStore()
const nationStore = useNationStore()

onMounted(() => {
  buildingStore.fetchState()
})

function isBuilt(id) {
  return buildingStore.built.includes(id)
}

function isUnlocked(building) {
  return buildingStore.researched.includes(building.requires_tech)
}

function isInProgress(id) {
  return buildingStore.currentBuilding === id
}

function requiredTechName(techId) {
  return techStore.tree.find((t) => t.id === techId)?.name || techId
}

function canAfford(building) {
  return nationStore.nation.treasury >= building.cost
}
</script>

<template>
  <div class="building-panel panel">
    <div class="panel-title">건물</div>
    <div v-if="buildingStore.error" class="error">{{ buildingStore.error }}</div>
    <div
      v-for="building in buildingStore.buildings"
      :key="building.id"
      class="building-card"
      :class="{
        done: isBuilt(building.id),
        locked: !isBuilt(building.id) && !isUnlocked(building),
        active: isInProgress(building.id),
      }"
    >
      <div class="building-name">
        {{ building.name }}
        <span v-if="isBuilt(building.id)" class="badge done-badge">완료</span>
        <span v-else-if="isInProgress(building.id)" class="badge active-badge">
          건설 중 · {{ buildingStore.currentBuildingMonthsLeft }}개월 남음
        </span>
      </div>
      <div class="building-desc">{{ building.description }}</div>
      <div v-if="!isUnlocked(building)" class="building-req">
        선행 기술: {{ requiredTechName(building.requires_tech) }}
      </div>
      <div class="building-footer">
        <span class="building-cost">{{ building.cost }} · {{ building.duration_months }}개월</span>
        <button
          v-if="!isBuilt(building.id) && !isInProgress(building.id)"
          :disabled="!isUnlocked(building) || !canAfford(building) || !!buildingStore.currentBuilding"
          @click="buildingStore.build(building.id)"
        >
          건설
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.building-panel {
  padding: 12px;
  width: 220px;
  flex-shrink: 0;
}
.panel-title {
  font-weight: bold;
  margin-bottom: 8px;
}
.error {
  color: var(--text-negative);
  font-size: 12px;
  margin-bottom: 8px;
}
.building-card {
  background: rgba(0, 0, 0, 0.22);
  border: 1px solid var(--panel-border-soft);
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 8px;
}
.building-card.done {
  border-color: var(--accent);
  background: var(--accent-dim);
}
.building-card.locked {
  opacity: 0.5;
}
.building-card.active {
  border-color: var(--accent-strong);
  background: rgba(255, 209, 102, 0.12);
}
.building-name {
  font-weight: bold;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.badge.done-badge {
  font-size: 10px;
  background: var(--accent);
  color: #241d12;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: normal;
}
.badge.active-badge {
  font-size: 10px;
  background: var(--accent-strong);
  color: #241d12;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: normal;
  white-space: nowrap;
}
.building-desc {
  font-size: 11px;
  color: var(--text-dim);
  margin-top: 2px;
}
.building-req {
  font-size: 11px;
  color: var(--text-faint);
  margin-top: 4px;
}
.building-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}
.building-cost {
  font-size: 12px;
  color: var(--accent-strong);
}
button {
  padding: 4px 10px;
  border-radius: 4px;
  border: 1px solid var(--panel-border-soft);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text);
  cursor: pointer;
  font-size: 12px;
  font-family: var(--font-body);
}
button:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent-strong);
}
button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
