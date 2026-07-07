<template>
  <section class="page-shell">
    <div class="toolbar">
      <div>
        <h1>我的资料</h1>
        <p>{{ user.username || "用户" }} · {{ roleLabel }}</p>
      </div>
      <button @click="loadData" :disabled="loading">{{ loading ? "加载中..." : "刷新" }}</button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="grid">
      <div class="panel">
        <h2>最近生成记录</h2>
        <table>
          <thead><tr><th>时间</th><th>文件</th><th>状态</th><th>记录数</th></tr></thead>
          <tbody>
            <tr v-for="item in generations.slice(0, 5)" :key="item.id">
              <td>{{ item.created_at }}</td><td>{{ item.file_name }}</td><td><span :class="['status', item.status]">{{ item.status }}</span></td><td>{{ item.record_count }}</td>
            </tr>
            <tr v-if="!generations.length"><td colspan="4">暂无记录</td></tr>
          </tbody>
        </table>
      </div>
      <div class="panel">
        <h2>最近操作记录</h2>
        <table>
          <thead><tr><th>时间</th><th>动作</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="item in operations.slice(0, 5)" :key="item.id">
              <td>{{ item.created_at }}</td><td>{{ item.action }}</td><td>{{ item.status_code }}</td>
            </tr>
            <tr v-if="!operations.length"><td colspan="3">暂无记录</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { getCurrentUser, getMyGenerations, getMyOperations } from "../api/request";

const user = ref({});
const generations = ref([]);
const operations = ref([]);
const loading = ref(false);
const error = ref("");
const roleLabel = computed(() => user.value.role === "admin" || user.value.is_admin ? "管理员" : "普通用户");

async function loadData() {
  loading.value = true;
  error.value = "";
  try {
    const [me, gen, ops] = await Promise.all([getCurrentUser(), getMyGenerations(), getMyOperations()]);
    user.value = me.data.user || {};
    localStorage.setItem("user", JSON.stringify(user.value));
    generations.value = gen.data.items || [];
    operations.value = ops.data.items || [];
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
.toolbar { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 16px; }
.toolbar button { padding: 8px 14px; border: none; border-radius: 6px; background: #2563eb; color: white; cursor: pointer; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
.panel { background: white; border-radius: 8px; padding: 18px; box-shadow: 0 8px 24px rgba(15,23,42,0.08); }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { border-bottom: 1px solid #e5e7eb; padding: 9px; text-align: left; }
th { background: #f8fafc; }
.status.SUCCESS { color: #15803d; font-weight: 700; }
.status.FAILED { color: #b91c1c; font-weight: 700; }
.error { color: #b91c1c; }
</style>
