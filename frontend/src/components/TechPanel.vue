<script setup>
import { onMounted, computed } from 'vue'
import { useTechStore } from '../stores/tech'
import { useNationStore } from '../stores/nation'

const techStore = useTechStore()
const nationStore = useNationStore()

onMounted(() => {
  techStore.fetchTree()
})

function isResearched(techId) {
  return techStore.researched.includes(techId)
}

function isAvailable(tech) {
  return tech.prereqs.every((p) => techStore.researched.includes(p))
}

function canAfford(tech) {
  return nationStore.nation.treasury >= tech.cost
}

function isInProgress(techId) {
  return techStore.currentResearch === techId
}

const prereqNames = computed(() => (tech) =>
  tech.prereqs
    .map((id) => techStore.tree.find((t) => t.id === id)?.name || id)
    .join(', '),
)
</script>

<template>
  <div class="tech-panel">
    <div class="panel-title">테크트리</div>
    <div v-if="techStore.error" class="error">{{ techStore.error }}</div>
    <div
      v-for="tech in techStore.tree"
      :key="tech.id"
      class="tech-card"
      :class="{
        done: isResearched(tech.id),
        locked: !isResearched(tech.id) && !isAvailable(tech),
        active: isInProgress(tech.id),
      }"
    >
      <div class="tech-name">
        {{ tech.name }}
        <span v-if="isResearched(tech.id)" class="badge done-badge">완료</span>
        <span v-else-if="isInProgress(tech.id)" class="badge active-badge">
          연구 중 · {{ techStore.currentResearchMonthsLeft }}개월 남음
        </span>
      </div>
      <div class="tech-desc">{{ tech.description }}</div>
      <div v-if="tech.prereqs.length" class="tech-prereq">선행: {{ prereqNames(tech) }}</div>
      <div class="tech-footer">
        <span class="tech-cost">{{ tech.cost }} · {{ tech.duration_months }}개월</span>
        <button
          v-if="!isResearched(tech.id) && !isInProgress(tech.id)"
          :disabled="!isAvailable(tech) || !canAfford(tech) || !!techStore.currentResearch"
          @click="techStore.research(tech.id)"
        >
          연구
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tech-panel {
  background: rgba(0, 0, 0, 0.6);
  color: white;
  padding: 12px;
  border-radius: 8px;
  font-family: sans-serif;
  width: 220px;
  flex-shrink: 0;
}
.panel-title {
  font-weight: bold;
  margin-bottom: 8px;
}
.error {
  color: #ff8080;
  font-size: 12px;
  margin-bottom: 8px;
}
.tech-card {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid #444;
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 8px;
}
.tech-card.done {
  border-color: #4a90d9;
  background: rgba(74, 144, 217, 0.15);
}
.tech-card.locked {
  opacity: 0.5;
}
.tech-card.active {
  border-color: #ffb84a;
  background: rgba(255, 184, 74, 0.12);
}
.tech-name {
  font-weight: bold;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.badge.done-badge {
  font-size: 10px;
  background: #4a90d9;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: normal;
}
.badge.active-badge {
  font-size: 10px;
  background: #ffb84a;
  color: #222;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: normal;
  white-space: nowrap;
}
.tech-desc {
  font-size: 11px;
  color: #ccc;
  margin-top: 2px;
}
.tech-prereq {
  font-size: 11px;
  color: #999;
  margin-top: 4px;
}
.tech-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}
.tech-cost {
  font-size: 12px;
  color: #ffd166;
}
button {
  padding: 4px 10px;
  border-radius: 4px;
  border: 1px solid #555;
  background: #333;
  color: white;
  cursor: pointer;
  font-size: 12px;
}
button:hover:not(:disabled) {
  background: #4a90d9;
  border-color: #4a90d9;
}
button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
