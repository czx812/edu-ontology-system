<template>
  <section class="page-shell">
    <div class="toolbar">
      <div>
        <h1>用户信息管理</h1>
        <p>查看普通用户和管理员账号信息，辅助权限核查与安全审计。</p>
      </div>
      <button :disabled="loading" @click="loadData">{{ loading ? "加载中..." : "刷新" }}</button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="filters">
      <input v-model="keyword" placeholder="按用户名或角色筛选" />
      <select v-model="role">
        <option value="">全部角色</option>
        <option value="user">普通用户</option>
        <option value="admin">管理员</option>
      </select>
    </div>

    <div class="stats-row">
      <div class="stat"><strong>{{ items.length }}</strong><span>账号总数</span></div>
      <div class="stat"><strong>{{ normalCount }}</strong><span>普通用户</span></div>
      <div class="stat"><strong>{{ adminCount }}</strong><span>管理员</span></div>
    </div>

    <div class="panel">
      <table>
        <thead><tr><th>ID</th><th>用户名</th><th>角色</th><th>权限</th><th>审计说明</th></tr></thead>
        <tbody>
          <tr v-for="item in filteredItems" :key="item.id">
            <td>{{ item.id }}</td>
            <td class="name">{{ item.username }}</td>
            <td>{{ item.role }}</td>
            <td><span :class="['badge', item.is_admin ? 'admin' : 'user']">{{ item.is_admin ? "管理员" : "普通用户" }}</span></td>
            <td>{{ item.is_admin ? "可查看系统级日志和全部生成记录" : "仅可访问个人工作台、个人记录和个人日志" }}</td>
          </tr>
          <tr v-if="!filteredItems.length"><td colspan="5">暂无用户</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { getAdminUsers } from "../api/request";

const items = ref([]);
const keyword = ref("");
const role = ref("");
const loading = ref(false);
const error = ref("");

const adminCount = computed(() => items.value.filter((item) => item.is_admin || item.role === "admin").length);
const normalCount = computed(() => items.value.length - adminCount.value);
const filteredItems = computed(() => {
  const q = keyword.value.trim().toLowerCase();
  return items.value.filter((item) => {
    const roleOk = !role.value || item.role === role.value || (role.value === "admin" && item.is_admin);
    const keywordOk = !q || [item.username, item.role, item.id].join(" ").toLowerCase().includes(q);
    return roleOk && keywordOk;
  });
});

async function loadData() {
  loading.value = true;
  error.value = "";
  try {
    const res = await getAdminUsers();
    items.value = res.data.items || [];
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || "加载用户信息失败";
  } finally {
    loading.value = false;
  }
}

onMounted(loadData);
</script>

<style scoped>
.page-shell { max-width: 1180px; margin: 0 auto; padding: 24px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 16px; }
.toolbar p { margin: 6px 0 0; color: #64748b; }
button { padding: 9px 14px; border: none; border-radius: 6px; background: #2563eb; color: white; cursor: pointer; }
.filters { display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
input, select { padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 6px; background: white; }
.stats-row { display: grid; grid-template-columns: repeat(3, minmax(120px, 1fr)); gap: 12px; margin-bottom: 14px; }
.stat { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; display: flex; flex-direction: column; gap: 4px; }
.stat strong { font-size: 22px; color: #0f172a; }
.stat span { color: #64748b; font-size: 13px; }
.panel { background: white; border-radius: 8px; padding: 18px; box-shadow: 0 8px 24px rgba(15,23,42,0.08); overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { border-bottom: 1px solid #e5e7eb; padding: 10px; text-align: left; vertical-align: top; }
th { background: #f8fafc; }
.name { font-weight: 700; color: #0f172a; }
.badge { display: inline-block; padding: 3px 8px; border-radius: 999px; font-size: 12px; }
.badge.admin { background: #fee2e2; color: #991b1b; }
.badge.user { background: #dcfce7; color: #166534; }
.error { color: #b91c1c; }
@media (max-width: 720px) { .toolbar { display: grid; } .stats-row { grid-template-columns: 1fr; } }
</style>
