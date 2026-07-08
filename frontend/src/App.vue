<template>
  <div>
    <aside v-if="isLoggedIn" class="app-sidebar">
      <div class="brand">
        <strong>教育本体系统</strong>
        <span>{{ isAdmin ? "管理员" : "普通用户" }} · {{ user.username || "用户" }}</span>
      </div>

      <nav class="nav-group">
        <router-link to="/dashboard">生成工作台</router-link>
        <router-link to="/sources">数据源检索</router-link>
        <router-link to="/audit">审计中心</router-link>
        <router-link to="/generations">本体文件记录</router-link>
        <router-link to="/profile">个人信息</router-link>
      </nav>

      <nav v-if="isAdmin" class="nav-group admin-group">
        <span class="group-title">系统管理</span>
        <router-link to="/admin/users">用户信息管理</router-link>
        <router-link to="/admin/logs">系统运行日志</router-link>
        <router-link to="/admin/generations">生成任务管理</router-link>
      </nav>

      <button class="logout" @click="logout">退出登录</button>
    </aside>

    <main :class="isLoggedIn ? 'app-main' : ''">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();

const user = computed(() => {
  route.fullPath;
  try {
    return JSON.parse(localStorage.getItem("user") || "{}");
  } catch (err) {
    return {};
  }
});

const isLoggedIn = computed(() => {
  route.fullPath;
  return Boolean(localStorage.getItem("token"));
});
const isAdmin = computed(() => user.value.is_admin || user.value.role === "admin" || user.value.username === "admin");

function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  router.push("/");
}
</script>

<style>
* { box-sizing: border-box; }
body { margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; color: #172033; background: #eef3f8; }
button, input, select { font: inherit; }
.app-sidebar { position: fixed; inset: 0 auto 0 0; width: 236px; background: #101828; color: #e5e7eb; padding: 18px 14px; display: flex; flex-direction: column; gap: 18px; z-index: 20; }
.brand { display: flex; flex-direction: column; gap: 6px; padding: 8px 8px 14px; border-bottom: 1px solid rgba(255,255,255,.12); }
.brand strong { font-size: 17px; }
.brand span { font-size: 12px; color: #aeb8c8; }
.nav-group { display: flex; flex-direction: column; gap: 6px; }
.group-title { padding: 8px; font-size: 12px; color: #94a3b8; }
.nav-group a { color: #cbd5e1; text-decoration: none; padding: 10px 12px; border-radius: 6px; border: 1px solid transparent; }
.nav-group a.router-link-active { color: white; background: #1d4ed8; border-color: #3b82f6; }
.nav-group a:hover { background: rgba(255,255,255,.08); }
.admin-group { border-top: 1px solid rgba(255,255,255,.12); padding-top: 10px; }
.logout { margin-top: auto; width: 100%; padding: 10px 12px; border: 1px solid #fecaca; border-radius: 6px; background: #fff1f2; color: #b91c1c; cursor: pointer; }
.app-main { min-height: 100vh; margin-left: 236px; }
@media (max-width: 820px) {
  .app-sidebar { position: static; width: 100%; min-height: auto; }
  .app-main { margin-left: 0; }
  .nav-group { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); }
  .logout { margin-top: 0; }
}
</style>
