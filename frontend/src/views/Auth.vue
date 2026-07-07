<template>
  <div class="page">
    <div class="card">
      <h1>教育本体生成系统</h1>
      <p class="subtitle">登录后上传 PDF，生成结构化数据、本体与 OWL 文件。</p>

      <div class="toggle">
        <button :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</button>
        <button :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</button>
      </div>

      <input v-model="username" placeholder="用户名" />
      <input v-model="password" type="password" placeholder="密码" />

      <button class="btn" :disabled="loading" @click="submit">
        {{ loading ? "处理中..." : mode === 'login' ? '登录' : '注册' }}
      </button>

      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { loginUser, registerUser } from "../api/request";

const router = useRouter();
const mode = ref("login");
const username = ref("");
const password = ref("");
const loading = ref(false);
const error = ref("");

async function submit() {
  if (!username.value || !password.value) {
    error.value = "用户名和密码不能为空";
    return;
  }

  loading.value = true;
  error.value = "";

  try {
    const res = mode.value === "login"
      ? await loginUser(username.value, password.value)
      : await registerUser(username.value, password.value);

    localStorage.setItem("token", res.data.token);
    localStorage.setItem("user", JSON.stringify(res.data.user || {}));
    router.push("/dashboard");
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || "操作失败";
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.page { min-height: 100vh; display: flex; justify-content: center; align-items: center; background: #eef6ff; }
.card { width: min(420px, calc(100vw - 32px)); padding: 32px; border-radius: 12px; background: white; box-shadow: 0 12px 32px rgba(15, 23, 42, 0.16); display: flex; flex-direction: column; gap: 12px; }
.subtitle { color: #64748b; margin-top: -6px; }
.toggle { display: flex; gap: 8px; }
.toggle button { flex: 1; padding: 8px; border-radius: 8px; border: 1px solid #cbd5e1; background: #f8fafc; cursor: pointer; }
.toggle button.active { background: #2563eb; color: white; border-color: #2563eb; }
input { padding: 10px; border-radius: 8px; border: 1px solid #cbd5e1; }
.btn { padding: 10px; border: none; border-radius: 8px; background: #16a34a; color: white; cursor: pointer; }
.btn:disabled { opacity: 0.7; cursor: not-allowed; }
.error { color: #b91c1c; }
</style>
