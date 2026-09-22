<script setup>
import { onMounted } from 'vue'
import { useDiplomacyStore } from '../stores/diplomacy'

const diplomacyStore = useDiplomacyStore()

const WORLD_ICON = { war: '⚔️', alliance: '🤝', peace: '·' }
const PERSONALITY_ICON = { aggressive: '⚔️', economic: '💰', isolationist: '🛡️' }
const PERSONALITY_LABEL = { aggressive: '호전적', economic: '경제 중심', isolationist: '고립주의' }

onMounted(async () => {
  // Sequential on purpose: for a brand-new session, both calls can trigger the
  // backend to seed the 3 rival rows on first read — firing them concurrently
  // raced two separate seed attempts and could leave duplicate rows behind.
  await diplomacyStore.fetchRivals()
  await diplomacyStore.fetchWorldRelationships()
})
</script>

<template>
  <div class="dip-panel panel">
    <div class="panel-title">외교</div>
    <div v-if="diplomacyStore.error" class="error">{{ diplomacyStore.error }}</div>
    <div
      v-for="r in diplomacyStore.rivals"
      :key="r.rival_id"
      class="rival-card"
      :class="{ war: r.relationship === 'war', defeated: r.relationship === 'defeated' }"
    >
      <div class="rival-name">
        {{ r.name }}
        <span class="badge" :class="r.relationship">
          {{
            r.relationship === 'war'
              ? `전쟁 ${r.war_months}개월째`
              : r.relationship === 'defeated'
                ? '멸망'
                : '평화'
          }}
        </span>
      </div>
      <div v-if="r.relationship !== 'defeated'" class="personality-row">
        {{ PERSONALITY_ICON[r.personality] || '·' }} {{ PERSONALITY_LABEL[r.personality] || r.personality }}
      </div>
      <div v-if="r.relationship !== 'defeated'" class="rival-stats">
        <span>경제 {{ r.economy }}</span>
        <span>안정 {{ r.stability }}</span>
        <span>군사 {{ r.military }}</span>
      </div>
      <button
        v-if="r.relationship === 'peace'"
        @click="diplomacyStore.declareWar(r.rival_id)"
      >
        선전포고
      </button>
      <button v-else-if="r.relationship === 'war'" @click="diplomacyStore.proposePeace(r.rival_id)">
        평화 제안
      </button>
    </div>

    <div v-if="diplomacyStore.worldRelationships.length" class="world-section">
      <div class="world-title">세계 정세</div>
      <div v-for="(w, i) in diplomacyStore.worldRelationships" :key="i" class="world-row">
        <span class="world-icon">{{ WORLD_ICON[w.relationship] || '·' }}</span>
        <span :class="{ dim: w.relationship === 'peace' }">
          {{ diplomacyStore.rivalName(w.rival_a) }} · {{ diplomacyStore.rivalName(w.rival_b) }}
        </span>
      </div>
    </div>

    <div v-if="diplomacyStore.lastReports.length" class="war-reports">
      <div v-for="(r, i) in diplomacyStore.lastReports" :key="i">⚔ {{ r }}</div>
    </div>
  </div>
</template>

<style scoped>
.dip-panel {
  padding: 12px;
  width: 220px;
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
.rival-card {
  background: rgba(0, 0, 0, 0.22);
  border: 1px solid var(--panel-border-soft);
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 8px;
}
.rival-card.war {
  border-color: var(--text-negative);
  background: rgba(226, 104, 90, 0.14);
}
.rival-card.defeated {
  opacity: 0.55;
}
.rival-name {
  font-weight: bold;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: normal;
  white-space: nowrap;
}
.badge.peace {
  background: var(--accent-dim);
  color: var(--accent-strong);
}
.badge.war {
  background: var(--text-negative);
  color: #241d12;
}
.badge.defeated {
  background: rgba(0, 0, 0, 0.4);
  color: var(--text-faint);
}
.personality-row {
  font-size: 11px;
  color: var(--accent);
  margin-top: 2px;
}
.rival-stats {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: var(--text-dim);
  margin: 4px 0 6px;
}
button {
  width: 100%;
  padding: 5px 10px;
  border-radius: 4px;
  border: 1px solid var(--panel-border-soft);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text);
  cursor: pointer;
  font-size: 12px;
  font-family: var(--font-body);
}
button:hover {
  border-color: var(--accent);
  color: var(--accent-strong);
}
.world-section {
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px solid var(--panel-border-soft);
}
.world-title {
  font-size: 12px;
  font-weight: bold;
  color: var(--text-dim);
  margin-bottom: 6px;
}
.world-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  padding: 2px 0;
  color: var(--text);
}
.world-row .dim {
  color: var(--text-faint);
}
.war-reports {
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-negative);
  border-top: 1px solid var(--panel-border-soft);
  padding-top: 6px;
}
</style>
