<script setup>
import { ref, watch } from 'vue'
import { useAuthStore } from '../stores/auth'

const authStore = useAuthStore()
const mode = ref('login') // 'login' | 'signup'

const username = ref('')
const password = ref('')
const displayName = ref('')
const usernameStatus = ref(null) // null | 'checking' | 'available' | 'taken'
const error = ref('')
const loading = ref(false)

watch(username, () => {
  usernameStatus.value = null
})

watch(mode, () => {
  error.value = ''
  usernameStatus.value = null
})

async function checkUsername() {
  const value = username.value.trim()
  if (!value) return
  usernameStatus.value = 'checking'
  const available = await authStore.checkUsername(value)
  usernameStatus.value = available ? 'available' : 'taken'
}

async function submit() {
  error.value = ''
  if (mode.value === 'signup' && usernameStatus.value !== 'available') {
    error.value = '아이디 중복 확인을 먼저 해주세요'
    return
  }
  loading.value = true
  try {
    if (mode.value === 'signup') {
      await authStore.signup(username.value.trim(), password.value, displayName.value.trim())
    } else {
      await authStore.login(username.value.trim(), password.value)
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-screen">
    <div class="card">
      <div class="brand">
        <div class="brand-icon">👑</div>
        <div class="brand-name">Regnum</div>
        <div class="brand-tagline">그대는 왕이 아니다. 왕의 곁을 지키는 조언자일 뿐.</div>
      </div>

      <div class="tabs">
        <button :class="{ active: mode === 'login' }" @click="mode = 'login'">로그인</button>
        <button :class="{ active: mode === 'signup' }" @click="mode = 'signup'">회원가입</button>
      </div>

      <form class="form" @submit.prevent="submit">
        <label class="field">
          <span>아이디</span>
          <div class="id-row">
            <input v-model="username" type="text" autocomplete="username" maxlength="20" />
            <button
              v-if="mode === 'signup'"
              type="button"
              class="check-btn"
              @click="checkUsername"
            >
              중복확인
            </button>
          </div>
          <span v-if="mode === 'signup' && usernameStatus" class="status" :class="usernameStatus">
            <template v-if="usernameStatus === 'checking'">확인 중...</template>
            <template v-else-if="usernameStatus === 'available'">사용 가능한 아이디입니다</template>
            <template v-else-if="usernameStatus === 'taken'">이미 사용 중인 아이디입니다</template>
          </span>
        </label>

        <label class="field">
          <span>비밀번호</span>
          <input v-model="password" type="password" autocomplete="current-password" />
        </label>

        <label v-if="mode === 'signup'" class="field">
          <span>이름</span>
          <input v-model="displayName" type="text" maxlength="20" placeholder="게임 안에서 쓰일 이름" />
        </label>

        <div v-if="error" class="error">{{ error }}</div>

        <button type="submit" class="submit-btn" :disabled="loading">
          {{ mode === 'signup' ? '회원가입하고 시작하기' : '로그인' }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-screen {
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
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
}
.brand {
  text-align: center;
  margin-bottom: 24px;
}
.brand-icon {
  font-size: 36px;
}
.brand-name {
  font-size: 26px;
  font-weight: bold;
  letter-spacing: 0.08em;
  background: linear-gradient(90deg, #ffd166, #f8f0d8);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  margin: 4px 0 6px;
}
.brand-tagline {
  font-size: 12px;
  color: #9aa3c0;
}
.tabs {
  display: flex;
  margin-bottom: 20px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #444;
}
.tabs button {
  flex: 1;
  padding: 10px;
  background: rgba(255, 255, 255, 0.03);
  color: #aaa;
  border: none;
  cursor: pointer;
  font-size: 14px;
}
.tabs button.active {
  background: #4a90d9;
  color: white;
  font-weight: bold;
}
.form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #cfd6ea;
}
.field input {
  padding: 10px 12px;
  border-radius: 6px;
  border: 1px solid #555;
  background: #1c2030;
  color: white;
  font-size: 14px;
}
.field input:focus {
  outline: none;
  border-color: #4a90d9;
}
.id-row {
  display: flex;
  gap: 6px;
}
.id-row input {
  flex: 1;
}
.check-btn {
  padding: 0 10px;
  border-radius: 6px;
  border: 1px solid #555;
  background: #333;
  color: white;
  cursor: pointer;
  font-size: 12px;
  white-space: nowrap;
}
.check-btn:hover {
  background: #4a90d9;
  border-color: #4a90d9;
}
.status {
  font-size: 12px;
}
.status.available {
  color: #4ade80;
}
.status.taken {
  color: #ff6b6b;
}
.status.checking {
  color: #999;
}
.error {
  color: #ff8080;
  font-size: 13px;
  text-align: center;
}
.submit-btn {
  margin-top: 6px;
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
