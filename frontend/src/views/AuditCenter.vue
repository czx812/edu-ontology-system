<template>
  <section class="page-shell">
    <div class="toolbar">
      <div>
        <h1>审计中心</h1>
        <p>集中查看生成、提问和操作记录，便于追踪普通用户行为与系统状态。</p>
      </div>
      <button :disabled="loading" @click="loadData">{{ loading ? "加载中..." : "刷新" }}</button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="stats-row">
      <div class="stat"><strong>{{ generations.length }}</strong><span>生成记录</span></div>
      <div class="stat"><strong>{{ questions.length }}</strong><span>提问记录</span></div>
      <div class="stat"><strong>{{ operations.length }}</strong><span>操作日志</span></div>
      <div class="stat"><strong>{{ failedGenerations }}</strong><span>失败任务</span></div>
    </div>

    <div class="tabs">
      <button :class="{ active: tab === 'generations' }" @click="tab = 'generations'">生成记录</button>
      <button :class="{ active: tab === 'questions' }" @click="tab = 'questions'">提问记录</button>
      <button :class="{ active: tab === 'operations' }" @click="tab = 'operations'">操作日志</button>
    </div>

    <div class="panel" v-if="tab === 'generations'">
      <table>
        <thead><tr><th>时间</th><th>文件</th><th>记录数</th><th>OWL</th><th>状态</th><th>耗时</th></tr></thead>
        <tbody>
          <tr v-for="item in generations" :key="item.id">
            <td>{{ item.created_at }}</td><td>{{ item.file_name }}</td><td>{{ item.record_count }}</td><td class="path">{{ item.owl_file }}</td><td><span :class="['status', item.status]">{{ item.status }}</span></td><td>{{ item.duration_ms }} ms</td>
          </tr>
          <tr v-if="!generations.length"><td colspan="6">暂无生成记录</td></tr>
        </tbody>
      </table>
    </div>

    <div class="panel" v-if="tab === 'questions'">
      <table>
        <thead><tr><th>时间</th><th>问题</th><th>回答摘要</th><th>状态</th></tr></thead>
        <tbody>
          <tr v-for="item in questions" :key="item.id">
            <td>{{ item.created_at }}</td><td>{{ item.question || item.prompt || '-' }}</td><td>{{ item.answer || item.response || '-' }}</td><td>{{ item.status || '-' }}</td>
          </tr>
          <tr v-if="!questions.length"><td colspan="4">暂无提问记录</td></tr>
        </tbody>
      </table>
    </div>

    <div class="panel" v-if="tab === 'operations'">
      <table>
        <thead><tr><th>时间</th><th>动作</th><th>接口</th><th>状态码</th><th>耗时</th><th>详情</th></tr></thead>
        <tbody>
          <tr v-for="item in operations" :key="item.id">
            <td>{{ item.created_at }}</td><td>{{ item.action }}</td><td>{{ item.path }}</td><td>{{ item.status_code }}</td><td>{{ item.duration_ms }} ms</td><td>{{ item.detail }}</td>
          </tr>
          <tr v-if="!operations.length"><td colspan="6">暂无操作日志</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { getMyGenerations, getMyOperations, getMyQuestions } from "../api/request";

const tab = ref("generations");
const generations = ref([]);
const operations = ref([]);
const questions = ref([]);
const loading = ref(false);
const error = ref("");
const failedGenerations = computed(() => generations.value.filter((item) => item.status === "FAILED").length);

async function loadData() {
  loading.value = true;
  error.value = "";
  try {
    const [gen, ops, q] = await Promise.all([getMyGenerations(), getMyOperations(), getMyQuestions()]);
    generations.value = gen.data.items || [];
    operations.value = ops.data.items || [];
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
.page-shell { max-width: 1180px; margin: 0 auto; padding: 24px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 16px; }
.toolbar p { margin: 6px 0 0; color: #64748b; }
button { padding: 9px 14px; border: none; border-radius: 6px; background: #2563eb; color: white; cursor: pointer; }
.stats-row { display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; margin-bottom: 14px; }
.stat { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; display: flex; flex-direction: column; gap: 4px; }
.stat strong { font-size: 22px; color: #0f172a; }
.stat span { color: #64748b; font-size: 13px; }
.tabs { display: flex; gap: 8px; margin-bottom: 14px; flex-wrap: wrap; }
.tabs button { background: #e2e8f0; color: #334155; }
.tabs button.active { background: #2563eb; color: white; }
.panel { background: white; border-radius: 8px; padding: 18px; box-shadow: 0 8px 24px rgba(15,23,42,0.08); overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { border-bottom: 1px solid #e5e7eb; padding: 10px; text-align: left; vertical-align: top; }
th { background: #f8fafc; }
.path { max-width: 260px; word-break: break-all; }
.status.SUCCESS { color: #15803d; font-weight: 700; }
.status.FAILED { color: #b91c1c; font-weight: 700; }
.error { color: #b91c1c; }
@media (max-width: 720px) { .toolbar { display: grid; } .stats-row { grid-template-columns: repeat(2, 1fr); } }
</style>
