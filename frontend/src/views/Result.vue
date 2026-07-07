<template>
  <div class="page">
    <div class="card">
      <h1>本体生成中心</h1>
      <button class="btn" :disabled="loading" @click="generate">
        {{ loading ? "正在生成..." : "开始生成" }}
      </button>
      <p v-if="error" class="error">{{ error }}</p>

      <div v-if="resultInfo" class="summary">
        <div><strong>结构化文件</strong><span>{{ resultInfo.structured_file || "-" }}</span></div>
        <div><strong>记录数</strong><span>{{ resultInfo.record_count }}</span></div>
        <div><strong>生成状态</strong><span>{{ resultInfo.generation_record?.status }}</span></div>
        <div><strong>耗时</strong><span>{{ resultInfo.generation_record?.duration_ms }} ms</span></div>
      </div>

      <pre v-if="ontology">{{ ontology }}</pre>

      <div v-if="traceSummary" class="trace-summary">
      <h2>数据溯源结果</h2>
        <p>结构化记录数：{{ traceSummary.total_records }}</p>
        <p>本体元素数：{{ traceSummary.total_trace_items }}</p>
        <p>已匹配来源：{{ traceSummary.matched_items }}</p>
        <p>未匹配来源：{{ traceSummary.unmatched_items }}</p>
        <p v-if="traceSummary.trace_file">溯源文件：{{ traceSummary.trace_file }}</p>
      </div>

      <pre v-if="traceMap" class="trace-json">{{ traceMap }}</pre>
      <button v-if="owlFile" class="btn2" @click="download">
        下载 OWL 文件
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRoute } from "vue-router";
import { generateOntology, exportOWL } from "../api/request";

const route = useRoute();
const filePath = route.query.filePath;

const ontology = ref("");
const traceMap = ref("");
const traceSummary = ref(null);
const owlFile = ref("");
const resultInfo = ref(null);
const loading = ref(false);
const error = ref("");

async function generate() {
  if (!filePath) {
    error.value = "缺少上传文件，请先返回上传 PDF。";
    return;
  }

  loading.value = true;
  error.value = "";
  ontology.value = "";
  traceMap.value = "";
  traceSummary.value = null;
  owlFile.value = "";
  resultInfo.value = null;

  try {
    const res = await generateOntology(filePath);
    ontology.value = JSON.stringify(res.data.ontology, null, 2);

    const trace = res.data.trace_map || {};
    traceMap.value = JSON.stringify(trace, null, 2);
    traceSummary.value = {
      total_records: trace.total_records || 0,
      total_trace_items: trace.total_trace_items || 0,
      matched_items: trace.matched_items || 0,
      unmatched_items: trace.unmatched_items || 0,
      trace_file: trace.trace_file || "",
    };

    owlFile.value = res.data.owl_file;
    resultInfo.value = res.data;
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || "生成失败，请查看后端日志。";
  } finally {
    loading.value = false;
  }
}

async function download() {
  if (!owlFile.value) {
    return;
  }
  const res = await exportOWL(owlFile.value);
  const url = window.URL.createObjectURL(new Blob([res.data]));
  const link = document.createElement("a");
  link.href = url;
  link.download = owlFile.value.split("/").pop();
  link.click();
  window.URL.revokeObjectURL(url);
}
</script>

<style scoped>
.page { min-height: calc(100vh - 58px); display: flex; justify-content: center; align-items: center; background: #eef6ff; padding: 24px; }
.card { background: white; padding: 32px; border-radius: 12px; width: min(820px, calc(100vw - 32px)); text-align: center; box-shadow: 0 10px 30px rgba(15,23,42,0.14); }
.btn, .btn2 { margin-top: 20px; padding: 10px 20px; border: none; color: white; border-radius: 8px; cursor: pointer; }
.btn { background: #2563eb; }
.btn:disabled { cursor: not-allowed; opacity: 0.7; }
.btn2 { margin-top: 15px; background: #16a34a; }
.error { margin-top: 16px; color: #b00020; word-break: break-word; }
.summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-top: 18px; text-align: left; }
.summary div { background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px; }
.summary strong, .summary span { display: block; word-break: break-all; }
.summary strong { color: #475569; margin-bottom: 4px; }
.trace-summary {
  margin-top: 20px;
  padding: 16px;
  border-radius: 10px;
  background: #f8f9ff;
  text-align: left;
  color: #333;
}

.trace-summary h2 {
  margin-top: 0;
}

.trace-summary p {
  margin: 6px 0;
}

.trace-json {
  max-height: 45vh;
}
pre { max-height: 55vh; overflow: auto; background: #f4f4f4; padding: 10px; margin-top: 20px; text-align: left; border-radius: 8px; }
</style>
