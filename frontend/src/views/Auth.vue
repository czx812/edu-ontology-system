<template>
  <div class="auth-page">
    <section class="intro">
      <h1>教育本体构建系统</h1>
      <p>面向普通用户的 PDF 本体生成、OWL 导出、数据源检索与安全审计工作台。</p>
      <div class="capabilities">
        <span>PDF 自动解析</span>
        <span>本体文件导出</span>
        <span>审计日志追踪</span>
      </div>
    </section>

    <section class="card">
      <h2>{{ mode === 'login' ? '用户登录' : '用户注册' }}</h2>
      <div class="toggle">
        <button :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</button>
        <button :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</button>
      </div>

      <label>用户名<input v-model="username" placeholder="请输入用户名" /></label>
      <label>密码<input v-model="password" type="password" placeholder="请输入密码" @keyup.enter="submit" /></label>

      <button class="submit" :disabled="loading" @click="submit">
        {{ loading ? "处理中..." : mode === 'login' ? '进入工作台' : '注册并进入' }}
      </button>

      <p v-if="error" class="error">{{ error }}</p>
    </section>
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
.auth-page { min-height: 100vh; display: grid; grid-template-columns: minmax(0, 1fr) 430px; gap: 32px; align-items: center; padding: 48px; background: #eef3f8; }
.intro { max-width: 720px; }
.intro h1 { margin: 0; font-size: 42px; color: #0f172a; }
.intro p { margin: 16px 0; color: #475569; font-size: 17px; line-height: 1.8; }
.capabilities { display: flex; gap: 10px; flex-wrap: wrap; }
.capabilities span { padding: 8px 10px; border-radius: 999px; background: white; border: 1px solid #dbeafe; color: #1d4ed8; font-size: 13px; }
.card { padding: 28px; border-radius: 8px; background: white; box-shadow: 0 16px 40px rgba(15,23,42,0.14); display: flex; flex-direction: column; gap: 14px; }
h2 { margin: 0; }
.toggle { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.toggle button { padding: 9px; border-radius: 6px; border: 1px solid #cbd5e1; background: #f8fafc; cursor: pointer; }
.toggle button.active { background: #2563eb; color: white; border-color: #2563eb; }
label { display: flex; flex-direction: column; gap: 6px; color: #334155; font-size: 14px; }
input { padding: 11px 12px; border-radius: 6px; border: 1px solid #cbd5e1; }
.submit { padding: 11px; border: none; border-radius: 6px; background: #16a34a; color: white; cursor: pointer; }
.submit:disabled { opacity: 0.7; cursor: not-allowed; }
.error { color: #b91c1c; margin: 0; }
@media (max-width: 860px) { .auth-page { grid-template-columns: 1fr; padding: 24px; } .intro h1 { font-size: 32px; } }
</style>
