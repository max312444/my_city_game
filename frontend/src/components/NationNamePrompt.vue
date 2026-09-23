<script setup>
import { ref } from 'vue'
import { useSessionStore } from '../stores/session'
import { useNationStore } from '../stores/nation'

const emit = defineEmits(['named'])
const sessionStore = useSessionStore()
const nationStore = useNationStore()

const name = ref('')
const difficulty = ref('normal')
const error = ref('')
const loading = ref(false)

const DIFFICULTIES = [
  { id: 'easy', icon: '🌱', label: '이지', description: '라이벌이 느리게 성장하고 좀처럼 먼저 싸움을 걸지 않아요' },
  { id: 'normal', icon: '⚖️', label: '노말', description: '기본 난이도예요' },
  { id: 'hard', icon: '🔥', label: '하드', description: '라이벌이 빠르게 성장하고 영토도 자주 넓혀요' },
  { id: 'hell', icon: '💀', label: '헬', description: '라이벌이 훨씬 강하게 성장하고 선전포고도 잦아요' },
]

async function submit() {
  const trimmed = name.value.trim()
  if (!trimmed) {
    error.value = '이름을 입력해주세요'
    return
  }
  error.value = ''
  loading.value = true
  try {
    const res = await fetch(
      `http://localhost:8000/api/session/${sessionStore.sessionId}/nation/name`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: trimmed, difficulty: difficulty.value }),
      },
    )
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '설정에 실패했습니다')
    nationStore.applyUpdate(data)
    emit('named')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="name-screen">
    <div class="card">
      <div class="brand-icon">🏛️</div>
      <div class="title">그대의 도시에 이름을 내리소서</div>
      <div class="subtitle">한 번 정하면 나중에 설정 메뉴에서 다시 바꿀 수 있어요</div>
      <input v-model="name" maxlength="20" placeholder="예: 서라벌" @keyup.enter="submit" />

      <div class="difficulty-label">난이도</div>
      <div class="difficulty-grid">
        <button
          v-for="d in DIFFICULTIES"
          :key="d.id"
          type="button"
          class="difficulty-btn"
          :class="{ active: difficulty === d.id }"
          :title="d.description"
          @click="difficulty = d.id"
        >
          <span class="difficulty-icon">{{ d.icon }}</span>
          <span>{{ d.label }}</span>
        </button>
      </div>
      <div class="difficulty-desc">{{ DIFFICULTIES.find((d) => d.id === difficulty)?.description }}</div>

      <div v-if="error" class="error">{{ error }}</div>
      <button class="submit-btn" :disabled="loading" @click="submit">시작하기</button>
    </div>
  </div>
</template>

<style scoped>
.name-screen {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-body);
  background: radial-gradient(ellipse at 50% 15%, #2a2013 0%, var(--bg-app) 70%);
  color: var(--text);
}
.card {
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  padding: 36px;
  border-radius: 10px;
  width: 340px;
  text-align: center;
  box-shadow: var(--panel-shadow);
}
.brand-icon {
  font-size: 36px;
  margin-bottom: 8px;
}
.title {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 6px;
  color: var(--accent-strong);
}
.subtitle {
  font-size: 12px;
  color: var(--text-dim);
  margin-bottom: 20px;
}
input {
  width: 100%;
  padding: 10px 12px;
  border-radius: 6px;
  border: 1px solid var(--panel-border-soft);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text);
  font-size: 14px;
  box-sizing: border-box;
  text-align: center;
  font-family: var(--font-body);
}
input:focus {
  outline: none;
  border-color: var(--accent);
}
.error {
  color: var(--text-negative);
  font-size: 13px;
  margin-top: 10px;
}
.difficulty-label {
  margin-top: 20px;
  font-size: 12px;
  color: var(--text-dim);
  text-align: left;
}
.difficulty-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  margin-top: 6px;
}
.difficulty-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 8px 4px;
  border-radius: 6px;
  border: 1px solid var(--panel-border-soft);
  background: rgba(0, 0, 0, 0.2);
  color: var(--text-dim);
  font-size: 12px;
  font-family: var(--font-body);
  cursor: pointer;
}
.difficulty-btn:hover {
  border-color: var(--accent);
}
.difficulty-btn.active {
  border-color: var(--accent);
  background: rgba(201, 162, 92, 0.18);
  color: var(--accent-strong);
  font-weight: bold;
}
.difficulty-icon {
  font-size: 16px;
}
.difficulty-desc {
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-faint);
  min-height: 28px;
}
.submit-btn {
  margin-top: 16px;
  width: 100%;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--accent);
  background: linear-gradient(180deg, var(--accent) 0%, #a9803e 100%);
  color: #241d12;
  font-weight: bold;
  font-size: 14px;
  cursor: pointer;
  font-family: var(--font-body);
}
.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.submit-btn:hover:not(:disabled) {
  filter: brightness(1.08);
}
</style>
