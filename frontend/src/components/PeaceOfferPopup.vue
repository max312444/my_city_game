<script setup>
import { computed, onMounted } from 'vue'
import { useDiplomacyStore } from '../stores/diplomacy'
import { useAdviceStore } from '../stores/advice'

const diplomacyStore = useDiplomacyStore()
const adviceStore = useAdviceStore()

onMounted(() => {
  diplomacyStore.fetchPeaceOffer()
})

// The advice banner spans the full width at the very bottom of the screen — shift
// this popup up out of its way instead of overlapping it when both are on screen.
const bottomOffset = computed(() => (adviceStore.currentAdvice ? '110px' : '16px'))
</script>

<template>
  <div
    v-if="diplomacyStore.pendingPeaceOffer"
    class="peace-offer panel"
    :style="{ bottom: bottomOffset }"
  >
    <div class="panel-title">평화 협정 제안</div>
    <div class="body">
      {{ diplomacyStore.pendingPeaceOffer.rival_name }}이(가) 장기전에 지쳐 평화 협정을 제안했습니다.
    </div>
    <div class="actions">
      <button class="accept" @click="diplomacyStore.respondPeaceOffer(true)">수락</button>
      <button class="reject" @click="diplomacyStore.respondPeaceOffer(false)">거절</button>
    </div>
  </div>
</template>

<style scoped>
.peace-offer {
  position: fixed;
  right: 16px;
  width: 260px;
  padding: 14px;
  z-index: 20;
  transition: bottom 0.2s ease;
}
.body {
  font-size: 13px;
  color: var(--text-dim);
  margin-bottom: 10px;
  line-height: 1.4;
}
.actions {
  display: flex;
  gap: 8px;
}
button {
  flex: 1;
  padding: 7px 10px;
  border-radius: 5px;
  border: 1px solid var(--panel-border-soft);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text);
  cursor: pointer;
  font-size: 13px;
  font-family: var(--font-body);
}
button.accept:hover {
  border-color: var(--accent);
  color: var(--accent-strong);
}
button.reject:hover {
  border-color: var(--text-negative);
  color: var(--text-negative);
}
</style>
