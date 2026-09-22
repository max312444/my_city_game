<script setup>
import { ref } from 'vue'
import { useNationStore } from '../stores/nation'
import { useClockStore } from '../stores/clock'
import { useSessionStore } from '../stores/session'

const API_BASE = 'http://localhost:8000'

const nationStore = useNationStore()
const clockStore = useClockStore()
const sessionStore = useSessionStore()

const dismissed = ref(false)
const restarting = ref(false)

function goToMainScreen() {
  clockStore.disconnect()
  sessionStore.setSessionId(null)
}

async function restart() {
  const confirmed = window.confirm('기존의 데이터가 사라집니다. 그래도 진행하시겠습니까?')
  if (!confirmed) return
  restarting.value = true
  try {
    await fetch(`${API_BASE}/api/session/${sessionStore.sessionId}`, { method: 'DELETE' })
    window.location.reload()
  } catch {
    restarting.value = false
  }
}
</script>

<template>
  <div v-if="!dismissed" class="victory-screen">
    <div class="card panel">
      <div class="crown">👑</div>
      <div class="title">천하 통일</div>
      <div class="subtitle">
        {{ nationStore.nation.name }}이(가) 대륙의 모든 세력을 무너뜨리고 유일한 국가로 남았습니다.
      </div>
      <div class="stats">
        <div>{{ clockStore.currentDate.year }}년 {{ clockStore.currentDate.month }}월 기준</div>
        <div>인구 {{ nationStore.nation.population }} · 경제 {{ nationStore.nation.economy }}</div>
        <div>군사 {{ nationStore.nation.military }} · 안정 {{ nationStore.nation.stability }}</div>
      </div>
      <div class="hint">이야기는 계속 이어집니다 — 아래에서 계속 관찰하거나 여기서 나갈 수 있습니다.</div>
      <div class="actions">
        <button class="action-btn" @click="dismissed = true">계속 관찰하기</button>
        <button class="action-btn" @click="goToMainScreen">메인 화면으로</button>
        <button class="restart-btn" :disabled="restarting" @click="restart">새로 시작하기</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.victory-screen {
  position: fixed;
  inset: 0;
  background: rgba(10, 8, 4, 0.82);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}
.card {
  width: min(90vw, 420px);
  padding: 32px 28px;
  text-align: center;
}
.crown {
  font-size: 40px;
  margin-bottom: 8px;
}
.title {
  font-family: var(--font-heading);
  font-size: 26px;
  font-weight: bold;
  color: var(--accent-strong);
  margin-bottom: 12px;
}
.subtitle {
  font-size: 14px;
  color: var(--text-dim);
  line-height: 1.5;
  margin-bottom: 18px;
}
.stats {
  font-size: 13px;
  color: var(--text);
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 0;
  border-top: 1px solid var(--panel-border-soft);
  border-bottom: 1px solid var(--panel-border-soft);
  margin-bottom: 14px;
}
.hint {
  font-size: 12px;
  color: var(--text-faint);
  margin-bottom: 18px;
}
.actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.action-btn,
.restart-btn {
  padding: 9px 12px;
  border-radius: 6px;
  border: 1px solid var(--panel-border-soft);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text);
  cursor: pointer;
  font-size: 13px;
  font-family: var(--font-body);
}
.action-btn:hover {
  border-color: var(--accent);
  color: var(--accent-strong);
}
.restart-btn {
  border-color: rgba(230, 160, 60, 0.5);
  color: #e6a03c;
}
.restart-btn:hover:not(:disabled) {
  border-color: #e6a03c;
  background: rgba(230, 160, 60, 0.12);
}
.restart-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
