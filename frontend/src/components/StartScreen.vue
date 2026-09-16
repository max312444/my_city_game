<script setup>
import { ref } from 'vue'
import { useSessionStore } from '../stores/session'

const API_BASE = 'http://localhost:8000'

const sessionStore = useSessionStore()
const name = ref('')
const checked = ref(false)
const exists = ref(false)
const checking = ref(false)

async function checkName() {
  const trimmed = name.value.trim()
  if (!trimmed) return
  checking.value = true
  const res = await fetch(`${API_BASE}/api/session/${encodeURIComponent(trimmed)}/exists`)
  const data = await res.json()
  exists.value = data.exists
  checked.value = true
  checking.value = false
}

function startGame() {
  sessionStore.setSessionId(name.value.trim())
}

async function startNewGame() {
  const trimmed = name.value.trim()
  if (exists.value) {
    if (!confirm('기존에 저장된 국가 데이터를 삭제하고 새로 시작할까요?')) return
    await fetch(`${API_BASE}/api/session/${encodeURIComponent(trimmed)}`, { method: 'DELETE' })
  }
  sessionStore.setSessionId(trimmed)
}

function backToNameInput() {
  checked.value = false
}
</script>

<template>
  <div class="start-screen">
    <div class="card">
      <div class="title">my_city</div>
      <div class="subtitle">국가의 이름을 입력하세요</div>

      <template v-if="!checked">
        <input
          v-model="name"
          type="text"
          placeholder="예: 조선"
          maxlength="20"
          @keyup.enter="checkName"
        />
        <button class="primary" :disabled="!name.trim() || checking" @click="checkName">
          확인
        </button>
      </template>

      <template v-else-if="exists">
        <div class="message">'{{ name.trim() }}'의 저장된 국가가 있습니다.</div>
        <button class="primary" @click="startGame">이어하기</button>
        <button class="secondary" @click="startNewGame">새로 만들기 (기존 데이터 삭제)</button>
        <button class="link" @click="backToNameInput">다른 이름으로</button>
      </template>

      <template v-else>
        <div class="message">'{{ name.trim() }}' 국가를 새로 시작합니다.</div>
        <button class="primary" @click="startNewGame">게임 시작</button>
        <button class="link" @click="backToNameInput">다른 이름으로</button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.start-screen {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: sans-serif;
  color: white;
}
.card {
  background: rgba(255, 255, 255, 0.06);
  padding: 32px;
  border-radius: 12px;
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.title {
  font-size: 24px;
  font-weight: bold;
  text-align: center;
}
.subtitle {
  color: #ccc;
  text-align: center;
  margin-bottom: 8px;
  font-size: 14px;
}
.message {
  color: #ddd;
  font-size: 14px;
  text-align: center;
  margin-bottom: 4px;
}
input {
  padding: 10px 12px;
  border-radius: 6px;
  border: 1px solid #555;
  background: #222;
  color: white;
  font-size: 15px;
}
button {
  padding: 10px 12px;
  border-radius: 6px;
  border: 1px solid #555;
  background: #333;
  color: white;
  cursor: pointer;
  font-size: 14px;
}
button.primary {
  background: #4a90d9;
  border-color: #4a90d9;
}
button.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
button.link {
  background: transparent;
  border: none;
  color: #999;
  text-decoration: underline;
}
</style>
