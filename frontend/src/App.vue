<template>
  <div>
    <nav v-if="isLoggedIn" class="top-nav">
      <router-link to="/dashboard">上传生成</router-link>
      <router-link to="/profile">我的记录</router-link>
      <router-link to="/logs">操作日志</router-link>
      <router-link to="/generations">生成记录</router-link>
      <router-link v-if="isAdmin" to="/admin/logs">日志管理</router-link>
      <router-link v-if="isAdmin" to="/admin/generations">生成记录管理</router-link>
      <button @click="logout">退出登录</button>
    </nav>
    <router-view />
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
body { margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; color: #1f2937; background: #f3f7ff; }
.top-nav { display: flex; gap: 10px; align-items: center; padding: 12px 24px; background: #ffffff; border-bottom: 1px solid #dbeafe; position: sticky; top: 0; z-index: 10; flex-wrap: wrap; }
.top-nav a, .top-nav button { padding: 8px 10px; border-radius: 6px; text-decoration: none; color: #1d4ed8; border: 1px solid transparent; background: transparent; cursor: pointer; font-size: 14px; }
.top-nav a.router-link-active { background: #dbeafe; border-color: #93c5fd; }
.top-nav button { margin-left: auto; color: #b91c1c; border-color: #fecaca; }
@media (max-width: 720px) { .top-nav button { margin-left: 0; } }
</style>
