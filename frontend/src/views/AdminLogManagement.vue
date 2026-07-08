<template>
  <section class="page-shell">
    <div class="toolbar">
      <div>
        <h1>系统运行日志</h1>
        <p>管理操作日志、提问记录和系统日志，用于监控与安全审计。</p>
      </div>
      <button :disabled="loading" @click="loadData">{{ loading ? "加载中..." : "刷新" }}</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>

    <div class="filters">
      <input v-model="filters.username" placeholder="用户名" />
      <input v-model="filters.action" placeholder="动作" />
      <button @click="loadData">筛选</button>
    </div>

    <div class="tabs">
      <button :class="{ active: tab === 'operations' }" @click="tab = 'operations'">操作日志</button>
      <button :class="{ active: tab === 'questions' }" @click="tab = 'questions'">提问记录</button>
      <button :class="{ active: tab === 'system' }" @click="tab = 'system'">系统日志</button>
    </div>

    <div class="panel" v-if="tab === 'operations'">
      <h2>操作日志</h2>
      <table>
        <thead><tr><th>时间</th><th>用户</th><th>动作</th><th>接口</th><th>状态</th><th>耗时</th><th>详情</th></tr></thead>
        <tbody>
          <tr v-for="item in operations" :key="item.id">
            <td>{{ item.created_at }}</td><td>{{ item.username }}</td><td>{{ item.action }}</td><td>{{ item.path }}</td><td>{{ item.status_code }}</td><td>{{ item.duration_ms }} ms</td><td>{{ item.detail }}</td>
          </tr>
          <tr v-if="!operations.length"><td colspan="7">暂无操作日志</td></tr>
        </tbody>
      </table>
    </div>

    <div class="panel" v-if="tab === 'questions'">
      <h2>提问记录</h2>
      <table>
        <thead><tr><th>时间</th><th>用户</th><th>问题</th><th>回答摘要</th><th>状态</th></tr></thead>
        <tbody>
          <tr v-for="item in questions" :key="item.id">
            <td>{{ item.created_at }}</td><td>{{ item.username }}</td><td>{{ item.question || item.prompt || '-' }}</td><td>{{ item.answer || item.response || '-' }}</td><td>{{ item.status || '-' }}</td>
          </tr>
          <tr v-if="!questions.length"><td colspan="5">暂无提问记录</td></tr>
        </tbody>
      </table>
    </div>

    <div class="panel" v-if="tab === 'system'">
      <h2>系统日志</h2>
      <pre>{{ systemLines.join('\n') || '暂无系统日志' }}</pre>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { getAdminOperationLogs, getAdminQuestionRecords, getAdminSystemLogs } from "../api/request";

const filters = reactive({ username: "", action: "" });
const tab = ref("operations");
const operations = ref([]);
const questions = ref([]);
const systemLines = ref([]);
const loading = ref(false);
const error = ref("");

async function loadData() {
  loading.value = true;
  error.value = "";
  try {
    const [ops, sys, q] = await Promise.all([
      getAdminOperationLogs({ page: 1, page_size: 50, username: filters.username, action: filters.action }),
      getAdminSystemLogs(),
      getAdminQuestionRecords({ page: 1, page_size: 50 }),
    ]);
    operations.value = ops.data.items || [];
    systemLines.value = sys.data.lines || [];
    questions.value = q.data.items || [];
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
.toolbar p { margin: 6px 0 0; color: #64748b; }
.filters { justify-content: flex-start; }
.tabs { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }
input { padding: 9px 10px; border: 1px solid #cbd5e1; border-radius: 6px; }
button { padding: 9px 14px; border: none; border-radius: 6px; background: #2563eb; color: white; cursor: pointer; }
.tabs button { background: #e2e8f0; color: #334155; }
.tabs button.active { background: #2563eb; color: white; }
.panel { background: white; border-radius: 8px; padding: 18px; box-shadow: 0 8px 24px rgba(15,23,42,0.08); overflow-x: auto; margin-bottom: 16px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { border-bottom: 1px solid #e5e7eb; padding: 9px; text-align: left; vertical-align: top; }
th { background: #f8fafc; }
pre { min-height: 220px; max-height: 420px; overflow: auto; background: #111827; color: #d1d5db; padding: 14px; border-radius: 6px; white-space: pre-wrap; }
.error { color: #b91c1c; }
</style>
