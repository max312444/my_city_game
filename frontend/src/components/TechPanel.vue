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
  <div class="tech-panel panel">
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
.tech-card {
  background: rgba(0, 0, 0, 0.22);
  border: 1px solid var(--panel-border-soft);
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 8px;
}
.tech-card.done {
  border-color: var(--accent);
  background: var(--accent-dim);
}
.tech-card.locked {
  opacity: 0.5;
}
.tech-card.active {
  border-color: var(--accent-strong);
  background: rgba(255, 209, 102, 0.12);
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
.tech-desc {
  font-size: 11px;
  color: var(--text-dim);
  margin-top: 2px;
}
.tech-prereq {
  font-size: 11px;
  color: var(--text-faint);
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
