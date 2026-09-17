<script setup>
import { onMounted } from 'vue'
import { useDiplomacyStore } from '../stores/diplomacy'

const diplomacyStore = useDiplomacyStore()

onMounted(() => {
  diplomacyStore.fetchRivals()
})
</script>

<template>
  <div class="dip-panel">
    <div class="panel-title">외교</div>
    <div v-if="diplomacyStore.error" class="error">{{ diplomacyStore.error }}</div>
    <div
      v-for="r in diplomacyStore.rivals"
      :key="r.rival_id"
      class="rival-card"
      :class="{ war: r.relationship === 'war' }"
    >
      <div class="rival-name">
        {{ r.name }}
        <span class="badge" :class="r.relationship">
          {{ r.relationship === 'war' ? `전쟁 ${r.war_months}개월째` : '평화' }}
        </span>
      </div>
      <div class="rival-stats">
        <span>경제 {{ r.economy }}</span>
        <span>안정 {{ r.stability }}</span>
        <span>군사 {{ r.military }}</span>
      </div>
      <button v-if="r.relationship === 'peace'" @click="diplomacyStore.declareWar(r.rival_id)">
        선전포고
      </button>
      <button v-else @click="diplomacyStore.proposePeace(r.rival_id)">평화 제안</button>
    </div>
    <div v-if="diplomacyStore.lastReports.length" class="war-reports">
      <div v-for="(r, i) in diplomacyStore.lastReports" :key="i">⚔ {{ r }}</div>
    </div>
  </div>
</template>

<style scoped>
.dip-panel {
  background: rgba(0, 0, 0, 0.6);
  color: white;
  padding: 12px;
  border-radius: 8px;
  font-family: sans-serif;
  width: 220px;
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
.rival-card {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid #444;
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 8px;
}
.rival-card.war {
  border-color: #e04040;
  background: rgba(224, 64, 64, 0.12);
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
}
.badge.peace {
  background: #4a90d9;
}
.badge.war {
  background: #e04040;
}
.rival-stats {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: #ccc;
  margin: 4px 0 6px;
}
button {
  width: 100%;
  padding: 5px 10px;
  border-radius: 4px;
  border: 1px solid #555;
  background: #333;
  color: white;
  cursor: pointer;
  font-size: 12px;
}
button:hover {
  background: #4a90d9;
  border-color: #4a90d9;
}
.war-reports {
  margin-top: 8px;
  font-size: 11px;
  color: #ffb0b0;
  border-top: 1px solid #444;
  padding-top: 6px;
}
</style>
