<template>
  <section class="page-shell">
    <div class="toolbar">
      <h1>操作日志</h1>
      <button :disabled="loading" @click="loadData">{{ loading ? "加载中..." : "刷新" }}</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="panel">
      <table>
        <thead>
          <tr><th>时间</th><th>动作</th><th>接口</th><th>状态码</th><th>耗时</th><th>详情</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td>{{ item.created_at }}</td>
            <td>{{ item.action }}</td>
            <td>{{ item.path }}</td>
            <td>{{ item.status_code }}</td>
            <td>{{ item.duration_ms }} ms</td>
            <td>{{ item.detail }}</td>
          </tr>
          <tr v-if="!items.length"><td colspan="6">暂无操作日志</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { getMyOperations } from "../api/request";

const items = ref([]);
const loading = ref(false);
const error = ref("");

async function loadData() {
  loading.value = true;
  error.value = "";
  try {
    const res = await getMyOperations();
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
.page-shell { max-width: 1180px; margin: 0 auto; padding: 24px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
button { padding: 8px 14px; border: none; border-radius: 6px; background: #2563eb; color: white; cursor: pointer; }
.panel { background: white; border-radius: 8px; padding: 18px; box-shadow: 0 8px 24px rgba(15,23,42,0.08); overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { border-bottom: 1px solid #e5e7eb; padding: 9px; text-align: left; vertical-align: top; }
th { background: #f8fafc; }
.error { color: #b91c1c; }
</style>
