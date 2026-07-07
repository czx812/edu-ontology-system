<template>
  <section class="page-shell">
    <div class="toolbar">
      <h1>生成记录管理</h1>
      <button :disabled="loading" @click="loadData">{{ loading ? "加载中..." : "刷新" }}</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>

    <div class="filters">
      <input v-model="filters.username" placeholder="用户名" />
      <select v-model="filters.status">
        <option value="">全部状态</option>
        <option value="SUCCESS">SUCCESS</option>
        <option value="FAILED">FAILED</option>
      </select>
      <button @click="loadData">筛选</button>
    </div>

    <div class="panel">
      <table>
        <thead>
          <tr><th>时间</th><th>用户</th><th>文件名</th><th>record_count</th><th>structured_file</th><th>owl_file</th><th>状态</th><th>错误信息</th><th>耗时</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td>{{ item.created_at }}</td>
            <td>{{ item.username }}</td>
            <td>{{ item.file_name }}</td>
            <td>{{ item.record_count }}</td>
            <td class="path">{{ item.structured_file }}</td>
            <td class="path">{{ item.owl_file }}</td>
            <td><span :class="['status', item.status]">{{ item.status }}</span></td>
            <td>{{ item.error_message }}</td>
            <td>{{ item.duration_ms }} ms</td>
          </tr>
          <tr v-if="!items.length"><td colspan="9">暂无生成记录</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { getAdminGenerationRecords } from "../api/request";

const filters = reactive({ username: "", status: "" });
const items = ref([]);
const loading = ref(false);
const error = ref("");

async function loadData() {
  loading.value = true;
  error.value = "";
  try {
    const res = await getAdminGenerationRecords({ page: 1, page_size: 50, username: filters.username, status: filters.status });
    items.value = res.data.items || [];
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
input, select { padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 6px; }
button { padding: 8px 14px; border: none; border-radius: 6px; background: #2563eb; color: white; cursor: pointer; }
.panel { background: white; border-radius: 8px; padding: 18px; box-shadow: 0 8px 24px rgba(15,23,42,0.08); overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { border-bottom: 1px solid #e5e7eb; padding: 9px; text-align: left; vertical-align: top; }
th { background: #f8fafc; }
.path { max-width: 220px; word-break: break-all; }
.status.SUCCESS { color: #15803d; font-weight: 700; }
.status.FAILED { color: #b91c1c; font-weight: 700; }
.error { color: #b91c1c; }
</style>
