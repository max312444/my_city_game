<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useNationStore } from '../stores/nation'
import { useGreatPeopleStore } from '../stores/greatPeople'
import { useGameLogStore } from '../stores/gameLog'
import { useSessionStore } from '../stores/session'
import { useClockStore } from '../stores/clock'

const API_BASE = 'http://localhost:8000'

const nationStore = useNationStore()
const greatPeopleStore = useGreatPeopleStore()
const gameLogStore = useGameLogStore()
const sessionStore = useSessionStore()

const open = ref(false)
const tab = ref('stats')
const bodyRef = ref(null)

const newCityName = ref('')
const renameError = ref('')
const renaming = ref(false)
const savedMessage = ref('')
const restarting = ref(false)

const LOG_ICONS = {
  tech: '📚',
  event: '⚡',
  great_person: '👑',
  war: '⚔️',
  world: '🌍',
  city: '🏛️',
  building: '🏗️',
  wonder: '🗿',
}

function toggle() {
  open.value = !open.value
}

async function selectTab(t) {
  tab.value = t
  if (t === 'greatpeople') greatPeopleStore.fetchHistory()
  if (t === 'log') {
    await gameLogStore.fetchLog()
    await nextTick()
    if (bodyRef.value) bodyRef.value.scrollTop = bodyRef.value.scrollHeight
  }
}

async function rename() {
  const trimmed = newCityName.value.trim()
  if (!trimmed) return
  renameError.value = ''
  renaming.value = true
  try {
    const res = await fetch(`${API_BASE}/api/session/${sessionStore.sessionId}/nation/name`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: trimmed }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '변경에 실패했습니다')
    nationStore.applyUpdate(data)
    newCityName.value = ''
  } catch (e) {
    renameError.value = e.message
  } finally {
    renaming.value = false
  }
}

function goToMainScreen() {
  open.value = false
  useClockStore().disconnect()
  sessionStore.setSessionId(null)
}

function showSaved() {
  savedMessage.value = '게임은 매달 자동으로 저장됩니다 — 현재 상태가 이미 저장되어 있습니다.'
  setTimeout(() => {
    savedMessage.value = ''
  }, 3500)
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
  <div class="menu-wrap">
    <button class="menu-btn panel" @click="toggle">☰ 메뉴</button>

    <div v-if="open" class="overlay" @click.self="open = false">
      <div class="modal panel">
        <div class="tabs">
          <button :class="{ active: tab === 'stats' }" @click="selectTab('stats')">국가 통계</button>
          <button :class="{ active: tab === 'greatpeople' }" @click="selectTab('greatpeople')">
            위인 명예전당
          </button>
          <button :class="{ active: tab === 'log' }" @click="selectTab('log')">게임 로그</button>
          <button :class="{ active: tab === 'settings' }" @click="selectTab('settings')">설정</button>
          <button class="close-btn" @click="open = false">✕</button>
        </div>

        <div class="body" ref="bodyRef">
          <div v-if="tab === 'stats'" class="stats-view">
            <div class="stat-row">
              <span class="label">인구</span><span class="value">{{ nationStore.nation.population }}</span>
            </div>
            <div class="stat-row">
              <span class="label">수용 인구</span
              ><span class="value">{{ nationStore.nation.land_capacity }}</span>
            </div>
            <div class="stat-row">
              <span class="label">인구 밀집도</span
              ><span class="value">{{ nationStore.nation.population_density }}%</span>
            </div>
            <div class="stat-row">
              <span class="label">도시 만족도</span
              ><span class="value">{{ nationStore.nation.satisfaction }}%</span>
            </div>
            <div class="section-divider"></div>
            <div class="stat-row">
              <span class="label">식량 생산</span
              ><span class="value">{{ nationStore.nation.food_production }}</span>
            </div>
            <div class="stat-row">
              <span class="label">식량 소비</span
              ><span class="value expense">-{{ nationStore.nation.food_consumption }}</span>
            </div>
            <div class="stat-row">
              <span class="label">식량 순생산</span>
              <span class="value" :class="{ negative: nationStore.nation.food_net < 0 }">{{
                nationStore.nation.food_net
              }}</span>
            </div>
            <div class="stat-row">
              <span class="label">식량 비축량</span>
              <span class="value" :class="{ negative: nationStore.nation.food_stock < 0 }">{{
                nationStore.nation.food_stock
              }}</span>
            </div>
            <div v-if="nationStore.nation.is_famine" class="warning">⚠ 기근 상태</div>
            <div class="section-divider"></div>
            <div class="stat-row">
              <span class="label">경제력</span><span class="value">{{ nationStore.nation.economy }}</span>
            </div>
            <div class="stat-row">
              <span class="label">안정도</span><span class="value">{{ nationStore.nation.stability }}</span>
            </div>
            <div class="stat-row">
              <span class="label">군사력</span><span class="value">{{ nationStore.nation.military }}</span>
            </div>
            <div class="stat-row">
              <span class="label">교육</span><span class="value">{{ nationStore.nation.education }}</span>
            </div>
            <div class="section-divider"></div>
            <div class="stat-row">
              <span class="label">월 수입</span
              ><span class="value">{{ nationStore.nation.monthly_income }}</span>
            </div>
            <div class="stat-row">
              <span class="label">월 지출</span
              ><span class="value expense">-{{ nationStore.nation.monthly_expenses }}</span>
            </div>
            <div class="stat-row">
              <span class="label">월 순수입</span>
              <span class="value" :class="{ negative: nationStore.nation.monthly_net < 0 }">{{
                nationStore.nation.monthly_net
              }}</span>
            </div>
            <div class="stat-row">
              <span class="label">보유 금액</span>
              <span class="value" :class="{ negative: nationStore.nation.treasury < 0 }">{{
                nationStore.nation.treasury
              }}</span>
            </div>
            <div v-if="nationStore.nation.is_bankrupt" class="warning">⚠ 파산 상태</div>
          </div>

          <div v-else-if="tab === 'greatpeople'" class="gp-view">
            <div v-if="greatPeopleStore.history.length === 0" class="empty">
              아직 등장한 위인이 없습니다.
            </div>
            <div v-for="p in [...greatPeopleStore.history].reverse()" :key="p.id" class="gp-row">
              <div class="gp-name">{{ p.name }} <span class="gp-title">({{ p.title }})</span></div>
              <div class="gp-date">{{ p.year }}년 {{ p.month }}월</div>
            </div>
          </div>

          <div v-else-if="tab === 'log'" class="log-view">
            <div v-if="gameLogStore.entries.length === 0" class="empty">
              아직 기록된 사건이 없습니다.
            </div>
            <div v-for="(e, i) in gameLogStore.entries" :key="i" class="log-row">
              <span class="log-icon">{{ LOG_ICONS[e.category] || '•' }}</span>
              <span class="log-date">{{ e.year }}년 {{ e.month }}월</span>
              <span class="log-message">{{ e.message }}</span>
            </div>
          </div>

          <div v-else-if="tab === 'settings'" class="settings-view">
            <label class="field">
              <span>도시 이름 변경</span>
              <div class="rename-row">
                <input v-model="newCityName" :placeholder="nationStore.nation.name" maxlength="20" />
                <button :disabled="renaming" @click="rename">변경</button>
              </div>
              <div v-if="renameError" class="error">{{ renameError }}</div>
            </label>

            <div class="section-divider"></div>

            <button class="action-btn" @click="goToMainScreen">메인 화면으로 돌아가기</button>
            <button class="action-btn" @click="showSaved">저장하기</button>
            <div v-if="savedMessage" class="saved-message">{{ savedMessage }}</div>
            <button class="restart-btn" :disabled="restarting" @click="restart">
              {{ restarting ? '초기화 중...' : '다시하기' }}
            </button>
            <button class="logout-btn" @click="goToMainScreen">로그아웃</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.menu-btn {
  width: 100%;
  padding: 10px;
  cursor: pointer;
  font-size: 13px;
  font-family: var(--font-body);
}
.menu-btn:hover {
  border-color: var(--accent);
  color: var(--accent-strong);
}
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 30;
}
.modal {
  width: 440px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}
.tabs {
  display: flex;
  border-bottom: 1px solid var(--panel-border-soft);
}
.tabs button {
  flex: 1;
  padding: 12px 6px;
  background: transparent;
  border: none;
  color: var(--text-dim);
  cursor: pointer;
  font-size: 12px;
  font-family: var(--font-body);
}
.tabs button.active {
  color: var(--accent-strong);
  border-bottom: 2px solid var(--accent-strong);
  font-weight: bold;
}
.close-btn {
  flex: 0 0 36px;
  color: var(--text-dim);
}
.body {
  padding: 16px;
  overflow-y: auto;
}
.stat-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 14px;
  padding: 3px 0;
}
.label {
  color: var(--text-dim);
}
.value {
  font-weight: bold;
}
.expense {
  color: var(--text-negative);
}
.negative {
  color: var(--text-negative);
}
.warning {
  margin-top: 8px;
  color: var(--text-negative);
  font-weight: bold;
  font-size: 13px;
  text-align: center;
}
.section-divider {
  border-top: 1px solid var(--panel-border-soft);
  margin: 8px 0;
}
.empty {
  font-size: 13px;
  color: var(--text-faint);
}
.gp-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  padding: 5px 0;
  border-bottom: 1px solid var(--panel-border-soft);
}
.gp-title {
  color: var(--text-dim);
  font-weight: normal;
}
.gp-date {
  color: var(--text-dim);
  white-space: nowrap;
}
.log-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 13px;
  padding: 5px 0;
  border-bottom: 1px solid var(--panel-border-soft);
}
.log-icon {
  flex: 0 0 auto;
}
.log-date {
  flex: 0 0 auto;
  color: var(--text-dim);
  white-space: nowrap;
  font-size: 12px;
}
.log-message {
  color: var(--text);
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--text-dim);
}
.rename-row {
  display: flex;
  gap: 6px;
}
.rename-row input {
  flex: 1;
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid var(--panel-border-soft);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text);
  font-family: var(--font-body);
}
.rename-row button {
  padding: 0 12px;
  border-radius: 6px;
  border: 1px solid var(--panel-border-soft);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text);
  cursor: pointer;
}
.rename-row button:hover {
  border-color: var(--accent);
  color: var(--accent-strong);
}
.error {
  color: var(--text-negative);
  font-size: 12px;
}
.action-btn {
  margin-top: 8px;
  width: 100%;
  padding: 10px;
  border-radius: 6px;
  border: 1px solid var(--panel-border-soft);
  background: rgba(0, 0, 0, 0.25);
  color: var(--text);
  cursor: pointer;
  font-family: var(--font-body);
}
.action-btn:hover {
  border-color: var(--accent);
  color: var(--accent-strong);
}
.saved-message {
  margin-top: 8px;
  font-size: 12px;
  color: var(--accent-strong);
  text-align: center;
}
.restart-btn {
  margin-top: 8px;
  width: 100%;
  padding: 10px;
  border-radius: 6px;
  border: 1px solid #a3702f;
  background: rgba(163, 112, 47, 0.18);
  color: #e0a860;
  cursor: pointer;
  font-family: var(--font-body);
}
.restart-btn:hover {
  background: rgba(163, 112, 47, 0.3);
}
.restart-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.logout-btn {
  margin-top: 8px;
  width: 100%;
  padding: 10px;
  border-radius: 6px;
  border: 1px solid #7a3535;
  background: rgba(122, 53, 53, 0.18);
  color: var(--text-negative);
  cursor: pointer;
  font-family: var(--font-body);
}
.logout-btn:hover {
  background: rgba(122, 53, 53, 0.3);
}
</style>
