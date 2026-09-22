<script setup>
import { ref } from 'vue'
import { useSessionStore } from '../stores/session'
import { useNationStore } from '../stores/nation'

const emit = defineEmits(['named'])
const sessionStore = useSessionStore()
const nationStore = useNationStore()

const name = ref('')
const error = ref('')
const loading = ref(false)

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
        body: JSON.stringify({ name: trimmed }),
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
