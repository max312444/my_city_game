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
  font-family: sans-serif;
  background: radial-gradient(circle at 50% 20%, #2a3550 0%, #14161f 70%);
  color: white;
}
.card {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 36px;
  border-radius: 14px;
  width: 340px;
  text-align: center;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
}
.brand-icon {
  font-size: 36px;
  margin-bottom: 8px;
}
.title {
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 6px;
}
.subtitle {
  font-size: 12px;
  color: #9aa3c0;
  margin-bottom: 20px;
}
input {
  width: 100%;
  padding: 10px 12px;
  border-radius: 6px;
  border: 1px solid #555;
  background: #1c2030;
  color: white;
  font-size: 14px;
  box-sizing: border-box;
  text-align: center;
}
input:focus {
  outline: none;
  border-color: #4a90d9;
}
.error {
  color: #ff8080;
  font-size: 13px;
  margin-top: 10px;
}
.submit-btn {
  margin-top: 16px;
  width: 100%;
  padding: 12px;
  border-radius: 8px;
  border: none;
  background: linear-gradient(90deg, #4a90d9, #6ab0f3);
  color: white;
  font-weight: bold;
  font-size: 14px;
  cursor: pointer;
}
.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.submit-btn:hover:not(:disabled) {
  filter: brightness(1.1);
}
</style>
