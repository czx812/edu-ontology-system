<template>
  <section class="page-shell">
    <div class="toolbar">
      <h1>本体生成记录</h1>
      <button :disabled="loading" @click="loadData">{{ loading ? "加载中..." : "刷新" }}</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="panel">
      <table>
        <thead>
          <tr><th>时间</th><th>文件名</th><th>结构化记录数</th><th>结构化文件</th><th>OWL 文件</th><th>状态</th><th>耗时</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td>{{ item.created_at }}</td>
            <td>{{ item.file_name }}</td>
            <td>{{ item.record_count }}</td>
            <td class="path">{{ item.structured_file }}</td>
            <td class="path">{{ item.owl_file }}</td>
            <td><span :class="['status', item.status]">{{ item.status }}</span></td>
            <td>{{ item.duration_ms }} ms</td>
          </tr>
          <tr v-if="!items.length"><td colspan="7">暂无生成记录</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { getMyGenerations } from "../api/request";

const items = ref([]);
const loading = ref(false);
const error = ref("");

async function loadData() {
  loading.value = true;
  error.value = "";
  try {
    const res = await getMyGenerations();
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
.path { max-width: 240px; word-break: break-all; }
.status.SUCCESS { color: #15803d; font-weight: 700; }
.status.FAILED { color: #b91c1c; font-weight: 700; }
.error { color: #b91c1c; }
</style>
