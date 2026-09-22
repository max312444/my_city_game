<script setup>
import { computed, onMounted, ref } from 'vue'
import { useTradeStore } from '../stores/trade'
import { useDiplomacyStore } from '../stores/diplomacy'

const tradeStore = useTradeStore()
const diplomacyStore = useDiplomacyStore()
const sellAmount = ref(10)

onMounted(() => {
  tradeStore.fetchState()
})

function routeFor(rivalId) {
  return tradeStore.routes.find((r) => r.rival_id === rivalId)
}

const sellableMax = computed(() =>
  Math.max(0, Math.floor(tradeStore.foodStock - tradeStore.foodSellMinReserve)),
)

async function sell() {
  const amount = Number(sellAmount.value)
  if (!amount || amount <= 0) return
  await tradeStore.sellFood(amount)
}
</script>

<template>
  <div class="trade-panel panel">
    <div class="panel-title">교역</div>
    <div v-if="tradeStore.error" class="error">{{ tradeStore.error }}</div>

    <div
      v-for="r in diplomacyStore.rivals.filter((x) => x.relationship !== 'defeated')"
      :key="r.rival_id"
      class="route-card"
      :class="{ active: routeFor(r.rival_id) }"
    >
      <div class="route-name">
        {{ r.name }}
        <span v-if="routeFor(r.rival_id) && r.relationship === 'peace'" class="badge active-badge">
          +{{ routeFor(r.rival_id).income }}/월
        </span>
        <span v-else-if="routeFor(r.rival_id)" class="badge suspended-badge">전쟁 중 · 중단</span>
      </div>
      <button
        v-if="!routeFor(r.rival_id) && r.relationship === 'peace'"
        @click="tradeStore.establish(r.rival_id)"
      >
        교역로 개설
      </button>
      <button v-else-if="routeFor(r.rival_id)" class="close-btn" @click="tradeStore.close(r.rival_id)">
        교역로 폐쇄
      </button>
      <div v-else class="route-hint">평화 시에만 교역로를 열 수 있습니다</div>
    </div>

    <div class="section-divider"></div>
    <div class="sell-title">식량 수출</div>
    <div class="sell-info">
      비축량 {{ tradeStore.foodStock }} · 판매가 {{ tradeStore.foodSellRate }}/단위 · 최소 비축
      {{ tradeStore.foodSellMinReserve }}
    </div>
    <div class="sell-row">
      <input v-model.number="sellAmount" type="number" min="1" :max="sellableMax" />
      <button :disabled="sellableMax <= 0" @click="sell">판매</button>
    </div>
  </div>
</template>

<style scoped>
.trade-panel {
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
.route-card {
  background: rgba(0, 0, 0, 0.22);
  border: 1px solid var(--panel-border-soft);
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 8px;
}
.route-card.active {
  border-color: var(--accent);
  background: var(--accent-dim);
}
.route-name {
  font-weight: bold;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-bottom: 6px;
}
.badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: normal;
  white-space: nowrap;
}
.badge.active-badge {
  background: var(--accent);
  color: #241d12;
}
.badge.suspended-badge {
  background: var(--text-negative);
  color: #241d12;
}
.route-hint {
  font-size: 11px;
  color: var(--text-faint);
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
button:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent-strong);
}
button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.close-btn:hover {
  border-color: var(--text-negative);
  color: var(--text-negative);
}
.section-divider {
  border-top: 1px solid var(--panel-border-soft);
  margin: 10px 0;
}
.sell-title {
  font-size: 12px;
  font-weight: bold;
  color: var(--text-dim);
  margin-bottom: 6px;
}
.sell-info {
  font-size: 11px;
  color: var(--text-faint);
  margin-bottom: 8px;
}
.sell-row {
  display: flex;
  gap: 6px;
}
.sell-row input {
  width: 70px;
  padding: 5px 6px;
  border-radius: 4px;
  border: 1px solid var(--panel-border-soft);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text);
  font-size: 12px;
  font-family: var(--font-body);
}
.sell-row button {
  flex: 1;
}
</style>
