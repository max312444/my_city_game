<script setup>
import { ref, onMounted } from 'vue'
import { useNationStore } from '../stores/nation'
import { useGreatPeopleStore } from '../stores/greatPeople'
import { useSessionStore } from '../stores/session'
import { useClockStore } from '../stores/clock'

const nationStore = useNationStore()
const greatPeopleStore = useGreatPeopleStore()
const sessionStore = useSessionStore()

const open = ref(false)
const tab = ref('stats')

const newCityName = ref('')
const renameError = ref('')
const renaming = ref(false)

function toggle() {
  open.value = !open.value
}

function selectTab(t) {
  tab.value = t
  if (t === 'greatpeople') greatPeopleStore.fetchHistory()
}

async function rename() {
  const trimmed = newCityName.value.trim()
  if (!trimmed) return
  renameError.value = ''
  renaming.value = true
  try {
    const res = await fetch(
      `http://localhost:8000/api/session/${sessionStore.sessionId}/nation/name`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: trimmed }),
      },
    )
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

function logout() {
  open.value = false
  useClockStore().disconnect()
  sessionStore.setSessionId(null)
}

onMounted(() => {
  greatPeopleStore.fetchHistory()
})
</script>

<template>
  <div class="menu-wrap">
    <button class="menu-btn" @click="toggle">☰ 메뉴</button>

    <div v-if="open" class="overlay" @click.self="open = false">
      <div class="modal">
        <div class="tabs">
          <button :class="{ active: tab === 'stats' }" @click="selectTab('stats')">국가 통계</button>
          <button :class="{ active: tab === 'greatpeople' }" @click="selectTab('greatpeople')">
            위인 명예전당
          </button>
          <button :class="{ active: tab === 'settings' }" @click="selectTab('settings')">설정</button>
          <button class="close-btn" @click="open = false">✕</button>
        </div>

        <div class="body">
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

          <div v-else-if="tab === 'settings'" class="settings-view">
            <label class="field">
              <span>도시 이름 변경</span>
              <div class="rename-row">
                <input v-model="newCityName" :placeholder="nationStore.nation.name" maxlength="20" />
                <button :disabled="renaming" @click="rename">변경</button>
              </div>
              <div v-if="renameError" class="error">{{ renameError }}</div>
            </label>
            <button class="logout-btn" @click="logout">로그아웃</button>
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
  border-radius: 8px;
  border: 1px solid #555;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  cursor: pointer;
  font-size: 13px;
  font-family: sans-serif;
}
.menu-btn:hover {
  background: #4a90d9;
  border-color: #4a90d9;
}
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 30;
}
.modal {
  background: #1a1d29;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  width: 360px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  font-family: sans-serif;
  color: white;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
}
.tabs {
  display: flex;
  border-bottom: 1px solid #333;
}
.tabs button {
  flex: 1;
  padding: 12px 6px;
  background: transparent;
  border: none;
  color: #999;
  cursor: pointer;
  font-size: 12px;
}
.tabs button.active {
  color: #ffd166;
  border-bottom: 2px solid #ffd166;
  font-weight: bold;
}
.close-btn {
  flex: 0 0 36px;
  color: #999;
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
  color: #ccc;
}
.value {
  font-weight: bold;
}
.expense {
  color: #e07070;
}
.negative {
  color: #e04040;
}
.warning {
  margin-top: 8px;
  color: #ff6b6b;
  font-weight: bold;
  font-size: 13px;
  text-align: center;
}
.section-divider {
  border-top: 1px solid #333;
  margin: 8px 0;
}
.empty {
  font-size: 13px;
  color: #999;
}
.gp-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  padding: 5px 0;
  border-bottom: 1px solid #2a2d3a;
}
.gp-title {
  color: #ccc;
  font-weight: normal;
}
.gp-date {
  color: #999;
  white-space: nowrap;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #cfd6ea;
}
.rename-row {
  display: flex;
  gap: 6px;
}
.rename-row input {
  flex: 1;
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid #555;
  background: #1c2030;
  color: white;
}
.rename-row button {
  padding: 0 12px;
  border-radius: 6px;
  border: 1px solid #555;
  background: #333;
  color: white;
  cursor: pointer;
}
.rename-row button:hover {
  background: #4a90d9;
  border-color: #4a90d9;
}
.error {
  color: #ff8080;
  font-size: 12px;
}
.logout-btn {
  margin-top: 20px;
  width: 100%;
  padding: 10px;
  border-radius: 6px;
  border: 1px solid #555;
  background: #3a2020;
  color: #ff8080;
  cursor: pointer;
}
.logout-btn:hover {
  background: #522828;
}
</style>
