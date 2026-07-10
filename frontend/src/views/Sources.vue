<template>
  <section class="sources-page">
    <div class="heading">
      <div>
        <h1>数据源检索</h1>
        <p>PDF 教育标准中的原始数据结构</p>
      </div>
      <button :disabled="loading" @click="loadSources">{{ loading ? "加载中..." : "刷新" }}</button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <div class="panel">
      <table>
        <thead><tr><th>编码</th><th>名称</th><th>类型</th><th>父类</th></tr></thead>
        <tbody>
          <tr v-for="item in rows" :key="item.code">
            <td class="code">{{ item.code }}</td>
            <td>{{ item.name }}</td>
            <td>{{ item.type }}</td>
            <td>{{ item.parent || "-" }}</td>
          </tr>
          <tr v-if="!rows.length && !loading"><td colspan="4">暂无标准数据</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { searchDataSources } from "../api/request";

const sourceMetadata = ref({ classes: [], properties: [] });
const loading = ref(false);
const error = ref("");
const rows = computed(() => [
  ...(sourceMetadata.value.classes || []),
  ...(sourceMetadata.value.properties || []),
]);

async function loadSources() {
  loading.value = true;
  error.value = "";
  try {
    const response = await searchDataSources();
    if (response.data.data_type !== "source") throw new Error("数据源接口类型错误");
    sourceMetadata.value = response.data.source_metadata || {
      classes: response.data.classes || [],
      properties: response.data.properties || [],
    };
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || "数据源加载失败";
  } finally {
    loading.value = false;
  }
}

onMounted(loadSources);
</script>

<style scoped>
.sources-page { max-width: 1100px; margin: 0 auto; padding: 28px; }
.heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
h1 { margin: 0; } p { color: #64748b; }
button { border: 0; border-radius: 6px; padding: 9px 16px; color: white; background: #2563eb; cursor: pointer; }
button:disabled { opacity: .6; cursor: wait; }
.error { color: #b91c1c; }
.panel { background: white; border-radius: 8px; padding: 18px; box-shadow: 0 8px 24px rgba(15,23,42,.08); overflow-x: auto; }
table { width: 100%; border-collapse: collapse; } th, td { padding: 11px; text-align: left; border-bottom: 1px solid #e5e7eb; }
th { background: #f8fafc; } .code { font-family: ui-monospace, monospace; white-space: nowrap; }
</style>
