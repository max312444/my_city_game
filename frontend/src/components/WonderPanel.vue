<script setup>
import { onMounted } from 'vue'
import { useWonderStore } from '../stores/wonders'
import { useTechStore } from '../stores/tech'
import { useDiplomacyStore } from '../stores/diplomacy'
import { useNationStore } from '../stores/nation'

const wonderStore = useWonderStore()
const techStore = useTechStore()
const diplomacyStore = useDiplomacyStore()
const nationStore = useNationStore()

onMounted(() => {
  wonderStore.fetchState()
})

function claimedBy(id) {
  return wonderStore.claims[id]
}

function claimedByLabel(id) {
  const builder = claimedBy(id)
  if (!builder) return ''
  return builder === 'player' ? '우리 국가' : diplomacyStore.rivalName(builder)
}

function isInProgress(id) {
  return wonderStore.currentWonder === id
}

function hasBoostTech(wonder) {
  return techStore.researched.includes(wonder.boost_tech)
}

function boostTechName(techId) {
  return techStore.tree.find((t) => t.id === techId)?.name || techId
}

function duration(wonder) {
  return hasBoostTech(wonder) ? wonder.fast_duration_months : wonder.base_duration_months
}

function canAfford(wonder) {
  return nationStore.nation.treasury >= wonder.cost
}
</script>

<template>
  <div class="wonder-panel panel">
    <div class="panel-title">문화유산</div>
    <div v-if="wonderStore.error" class="error">{{ wonderStore.error }}</div>
    <div v-if="wonderStore.lastEvent" class="event-toast">🏛️ {{ wonderStore.lastEvent }}</div>
    <div
      v-for="wonder in wonderStore.wonders"
      :key="wonder.id"
      class="wonder-card"
      :class="{
        done: !!claimedBy(wonder.id),
        lost: claimedBy(wonder.id) && claimedBy(wonder.id) !== 'player',
        active: isInProgress(wonder.id),
      }"
    >
      <div class="wonder-name">
        {{ wonder.name }}
        <span v-if="claimedBy(wonder.id) === 'player'" class="badge done-badge">완성</span>
        <span v-else-if="claimedBy(wonder.id)" class="badge lost-badge">{{ claimedByLabel(wonder.id) }} 완성</span>
        <span v-else-if="isInProgress(wonder.id)" class="badge active-badge">
          건설 중 · {{ wonderStore.currentWonderMonthsLeft }}개월 남음
        </span>
      </div>
      <div class="wonder-desc">{{ wonder.description }}</div>
      <div v-if="!claimedBy(wonder.id)" class="wonder-boost">
        {{ boostTechName(wonder.boost_tech) }} 연구 시 {{ wonder.fast_duration_months }}개월,
        아니면 {{ wonder.base_duration_months }}개월
      </div>
      <div class="wonder-footer">
        <span class="wonder-cost">{{ wonder.cost }} · {{ duration(wonder) }}개월</span>
        <button
          v-if="!claimedBy(wonder.id) && !isInProgress(wonder.id)"
          :disabled="!canAfford(wonder) || !!wonderStore.currentWonder"
          @click="wonderStore.start(wonder.id)"
        >
          건설
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wonder-panel {
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
.event-toast {
  font-size: 11px;
  color: var(--accent-strong);
  background: rgba(0, 0, 0, 0.25);
  border-radius: 5px;
  padding: 6px 8px;
  margin-bottom: 8px;
}
.wonder-card {
  background: rgba(0, 0, 0, 0.22);
  border: 1px solid var(--panel-border-soft);
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 8px;
}
.wonder-card.done {
  border-color: var(--accent);
  background: var(--accent-dim);
}
.wonder-card.lost {
  opacity: 0.55;
}
.wonder-card.active {
  border-color: var(--accent-strong);
  background: rgba(255, 209, 102, 0.12);
}
.wonder-name {
  font-weight: bold;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.badge.done-badge {
  font-size: 10px;
  background: var(--accent);
  color: #241d12;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: normal;
}
.badge.lost-badge {
  font-size: 10px;
  background: var(--text-negative);
  color: #241d12;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: normal;
  white-space: nowrap;
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
.wonder-desc {
  font-size: 11px;
  color: var(--text-dim);
  margin-top: 2px;
}
.wonder-boost {
  font-size: 11px;
  color: var(--text-faint);
  margin-top: 4px;
}
.wonder-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}
.wonder-cost {
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
