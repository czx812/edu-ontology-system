<template>
  <section class="page-shell">
    <div class="toolbar">
      <h1>日志管理</h1>
      <button :disabled="loading" @click="loadData">{{ loading ? "加载中..." : "刷新" }}</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>

    <div class="filters">
      <input v-model="filters.username" placeholder="用户名" />
      <input v-model="filters.action" placeholder="动作" />
      <button @click="loadData">筛选</button>
    </div>

    <div class="panel">
      <h2>操作日志</h2>
      <table>
        <thead>
          <tr><th>时间</th><th>用户</th><th>动作</th><th>接口</th><th>状态</th><th>耗时</th><th>详情</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in operations" :key="item.id">
            <td>{{ item.created_at }}</td><td>{{ item.username }}</td><td>{{ item.action }}</td><td>{{ item.path }}</td><td>{{ item.status_code }}</td><td>{{ item.duration_ms }} ms</td><td>{{ item.detail }}</td>
          </tr>
          <tr v-if="!operations.length"><td colspan="7">暂无操作日志</td></tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <h2>系统日志</h2>
      <pre>{{ systemLines.join('\n') || '暂无系统日志' }}</pre>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { getAdminOperationLogs, getAdminSystemLogs } from "../api/request";

const filters = reactive({ username: "", action: "" });
const operations = ref([]);
const systemLines = ref([]);
const loading = ref(false);
const error = ref("");

async function loadData() {
  loading.value = true;
  error.value = "";
  try {
    const [ops, sys] = await Promise.all([
      getAdminOperationLogs({ page: 1, page_size: 50, username: filters.username, action: filters.action }),
      getAdminSystemLogs(),
    ]);
    operations.value = ops.data.items || [];
    systemLines.value = sys.data.lines || [];
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || "加载失败";
  } finally {
    loading.value = false;
  }
}

onMounted(loadData);
</script>

<style scoped>
.page-shell { max-width: 1220px; margin: 0 auto; padding: 24px; }
.toolbar, .filters { display: flex; gap: 10px; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
.filters { justify-content: flex-start; }
input { padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 6px; }
button { padding: 8px 14px; border: none; border-radius: 6px; background: #2563eb; color: white; cursor: pointer; }
.panel { background: white; border-radius: 8px; padding: 18px; box-shadow: 0 8px 24px rgba(15,23,42,0.08); overflow-x: auto; margin-bottom: 16px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { border-bottom: 1px solid #e5e7eb; padding: 9px; text-align: left; vertical-align: top; }
th { background: #f8fafc; }
pre { min-height: 220px; max-height: 420px; overflow: auto; background: #111827; color: #d1d5db; padding: 14px; border-radius: 6px; white-space: pre-wrap; }
.error { color: #b91c1c; }
</style>
