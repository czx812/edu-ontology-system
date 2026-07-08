<template>
  <section class="page-shell">
    <div class="toolbar">
      <div>
        <h1>本体生成与导出</h1>
        <p class="path">{{ filePath || "请先上传 PDF 文档" }}</p>
        <p class="hint">{{ modeLabel }}</p>
      </div>

      <div class="actions">
        <button class="primary" :disabled="loading || !filePath" @click="generate">
          {{ loading ? "生成中..." : "开始生成" }}
        </button>
        <button class="success" :disabled="!owlFile" @click="download">导出 OWL</button>
        <button class="secondary" :disabled="!ontology" @click="goSources">检索数据源</button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="timeoutFallback" class="timeout-warning">
      规则初始本体已生成，大模型轻量增强超时，当前为规则兜底结果。
    </div>

    <div v-if="progress" class="progress-panel">
      <div class="progress-head">
        <strong>{{ progress.current_step_label || "生成进度" }}</strong>
        <span>{{ progress.progress_percent || 0 }}%</span>
      </div>

      <div class="bar">
        <div :style="{ width: `${progress.progress_percent || 0}%` }"></div>
      </div>

      <div class="progress-grid">
        <div><strong>status</strong><span>{{ progress.status || "-" }}</span></div>
        <div><strong>stage</strong><span>{{ progress.current_step || "-" }}</span></div>
        <div><strong>elapsed</strong><span>{{ progress.elapsed_seconds || 0 }} s</span></div>
        <div><strong>generation_mode</strong><span>{{ progress.stats?.generation_mode ?? "-" }}</span></div>
        <div><strong>total_records</strong><span>{{ progress.stats?.total_records ?? 0 }}</span></div>
        <div><strong>datatype_properties</strong><span>{{ progress.stats?.datatype_properties ?? 0 }}</span></div>
        <div><strong>classes</strong><span>{{ progress.stats?.classes ?? 0 }}</span></div>
        <div><strong>object_properties</strong><span>{{ progress.stats?.object_properties ?? 0 }}</span></div>
        <div><strong>relations</strong><span>{{ progress.stats?.relations ?? 0 }}</span></div>
        <div><strong>source_mappings</strong><span>{{ progress.stats?.source_mappings ?? 0 }}</span></div>
        <div><strong>alignment_mappings</strong><span>{{ progress.stats?.alignment_mappings ?? 0 }}</span></div>
        <div><strong>llm_calls</strong><span>{{ progress.stats?.llm_calls ?? 0 }}</span></div>
        <div><strong>llm_duration_ms</strong><span>{{ progress.stats?.llm_duration_ms ?? 0 }}</span></div>
      </div>

      <div v-if="progress.warnings?.length" class="warnings">
        <strong>warnings</strong>
        <div v-for="warning in progress.warnings" :key="warning">{{ warning }}</div>
      </div>
    </div>

    <div class="stats-row">
      <div class="stat"><strong>{{ stats.classes }}</strong><span>类</span></div>
      <div class="stat"><strong>{{ stats.properties }}</strong><span>属性</span></div>
      <div class="stat"><strong>{{ stats.relations }}</strong><span>关系</span></div>
      <div class="stat"><strong>{{ recordCount }}</strong><span>结构化记录</span></div>
    </div>

    <div v-if="resultInfo" class="summary">
      <div><strong>结构化文件</strong><span>{{ resultInfo.structured_file || "-" }}</span></div>
      <div><strong>记录数</strong><span>{{ resultInfo.record_count || 0 }}</span></div>
      <div><strong>生成状态</strong><span>{{ resultInfo.generation_record?.status || "-" }}</span></div>
      <div><strong>耗时</strong><span>{{ resultInfo.generation_record?.duration_ms || 0 }} ms</span></div>
      <div v-for="item in statItems" :key="item.key">
        <strong>{{ item.key }}</strong>
        <span>{{ item.value }}</span>
      </div>
    </div>

    <div class="panel-grid">
      <div class="panel">
        <h2>生成状态</h2>
        <dl>
          <dt>状态</dt>
          <dd>{{ statusText }}</dd>

          <dt>OWL 文件</dt>
          <dd class="path">{{ owlFile || "尚未生成" }}</dd>

          <dt>结构化文件</dt>
          <dd class="path">{{ structuredFile || "尚未生成" }}</dd>

          <dt>生成模式</dt>
          <dd>{{ ontology?.metadata?.generation_mode || ontology?.stats?.generation_mode || "-" }}</dd>

          <dt>LLM</dt>
          <dd>{{ ontology?.metadata?.llm_provider || ontology?.stats?.llm_provider || "-" }} {{ ontology?.metadata?.llm_model || ontology?.stats?.llm_model || "" }}</dd>
        </dl>
      </div>

      <div class="panel">
        <h2>导出说明</h2>
        <p>
          生成完成后可下载 OWL 文件，也可以进入数据源检索页面按类、属性、关系和来源文件追踪本体依据。
        </p>
      </div>
    </div>

    <div v-if="traceSummary" class="trace-summary">
      <h2>数据溯源结果</h2>
      <p>结构化记录数：{{ traceSummary.total_records }}</p>
      <p>本体元素数：{{ traceSummary.total_trace_items }}</p>
      <p>已匹配来源：{{ traceSummary.matched_items }}</p>
      <p>未匹配来源：{{ traceSummary.unmatched_items }}</p>
      <p v-if="traceSummary.trace_file">溯源文件：{{ traceSummary.trace_file }}</p>
    </div>

    <div class="panel preview" v-if="ontology">
      <h2>本体 JSON 预览</h2>
      <pre>{{ prettyOntology }}</pre>
    </div>

    <div class="panel preview" v-if="traceMap">
      <h2>溯源 JSON 预览</h2>
      <pre>{{ traceMap }}</pre>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  exportOWL,
  getGenerationProgress,
  getGenerationResult,
  startGeneration,
} from "../api/request";

const route = useRoute();
const router = useRouter();

const filePath = route.query.filePath || localStorage.getItem("lastUploadedPdf") || "";
const mode = computed(() => route.query.mode || "rule_draft_llm_enhance");
const forceRegenerate = computed(() => route.query.forceRegenerate === "true");
const maxGroupRecords = computed(() => Number(route.query.maxGroupRecords || 80));

const ontology = ref(null);
const owlFile = ref("");
const structuredFile = ref("");
const resultInfo = ref(null);
const progress = ref(null);
const traceMap = ref("");
const traceSummary = ref(null);
const loading = ref(false);
const error = ref("");

let timer = null;

const modeLabel = computed(() => {
  if (mode.value === "group_llm") return "深度全量生成，耗时较长";
  if (mode.value === "rule_only") return "纯规则备用模式";
  if (mode.value === "smoke_llm") return "仅测试大模型调用";
  return "大模型优先快速生成";
});

const llmInfo = computed(() => {
  const ontologyData = resultInfo.value?.ontology || ontology.value || {};
  return {
    ...(ontologyData.stats || {}),
    ...(ontologyData.metadata || {}),
  };
});

const statItems = computed(() =>
  [
    "generation_mode",
    "generation_strategy",
    "total_records",
    "datatype_properties",
    "classes",
    "object_properties",
    "relations",
    "source_mappings",
    "alignment_mappings",
    "llm_calls",
    "llm_duration_ms",
    "content_extract_ok",
    "llm_error_type",
    "cache_hit",
    "enhance_cache_hit",
    "timeout_reached",
  ].map((key) => ({
    key,
    value: llmInfo.value[key] ?? "-",
  }))
);

const timeoutFallback = computed(() => {
  return (
    progress.value?.stats?.generation_mode === "llm_timeout_fallback" ||
    llmInfo.value.generation_mode === "llm_timeout_fallback"
  );
});

const stats = computed(() => ({
  classes:
    ontology.value?.classes?.length ||
    ontology.value?.stats?.classes ||
    progress.value?.stats?.classes ||
    0,

  properties:
    ontology.value?.properties?.length ||
    ontology.value?.stats?.datatype_properties ||
    progress.value?.stats?.datatype_properties ||
    0,

  relations:
    ontology.value?.relations?.length ||
    ontology.value?.stats?.relations ||
    progress.value?.stats?.relations ||
    0,
}));

const recordCount = computed(() => {
  return (
    resultInfo.value?.record_count ||
    ontology.value?.stats?.total_records ||
    progress.value?.stats?.total_records ||
    0
  );
});

const statusText = computed(() => {
  if (loading.value) return "正在生成";
  if (error.value) return "生成失败";
  if (ontology.value) return "生成成功";
  return "等待生成";
});

const prettyOntology = computed(() => {
  if (!ontology.value) return "";
  return JSON.stringify(ontology.value, null, 2);
});

async function generate() {
  if (!filePath) {
    error.value = "缺少上传文件，请先返回上传 PDF。";
    return;
  }

  loading.value = true;
  error.value = "";
  ontology.value = null;
  traceMap.value = "";
  traceSummary.value = null;
  owlFile.value = "";
  structuredFile.value = "";
  resultInfo.value = null;
  progress.value = null;

  try {
    const start = await startGeneration(filePath, {
      mode: mode.value,
      force_regenerate: forceRegenerate.value,
      max_group_records: maxGroupRecords.value,
      enable_review: false,
      enable_alignment: true,
      enable_deep_alignment: false,
      enable_global_merge: false,
      enable_cache: true,
      max_generation_seconds: 180,
      llm_single_call_timeout: 45,
    });

    progress.value = start.data;
    poll(start.data.job_id);
  } catch (err) {
    loading.value = false;
    error.value = displayError(err);
  }
}

function poll(jobId) {
  clearInterval(timer);

  timer = setInterval(async () => {
    try {
      const res = await getGenerationProgress(jobId);
      progress.value = res.data;

      if (res.data.status === "success") {
        clearInterval(timer);

        const result = await getGenerationResult(jobId);
        setResult(result.data);

        loading.value = false;
      } else if (res.data.status === "failed") {
        clearInterval(timer);

        loading.value = false;
        error.value = displayErrorText(res.data.error || res.data.message || "生成失败。");
      }
    } catch (err) {
      clearInterval(timer);

      loading.value = false;
      error.value = displayError(err);
    }
  }, 1500);
}

function setResult(data) {
  resultInfo.value = data;
  ontology.value = data.ontology || null;
  owlFile.value = data.owl_file || "";
  structuredFile.value = data.structured_file || "";

  if (owlFile.value) {
    localStorage.setItem("lastOwlFile", owlFile.value);
  }

  if (structuredFile.value) {
    localStorage.setItem("lastStructuredFile", structuredFile.value);
  }

  if (ontology.value) {
    localStorage.setItem("lastOntology", JSON.stringify(ontology.value));
  }

  const trace = data.trace_map || {};
  traceMap.value = Object.keys(trace).length ? JSON.stringify(trace, null, 2) : "";

  traceSummary.value = Object.keys(trace).length
    ? {
        total_records: trace.total_records || 0,
        total_trace_items: trace.total_trace_items || 0,
        matched_items: trace.matched_items || 0,
        unmatched_items: trace.unmatched_items || 0,
        trace_file: trace.trace_file || data.trace_file || "",
      }
    : null;
}

function displayError(err) {
  return displayErrorText(err.response?.data?.detail || err.message || "生成失败。");
}

function displayErrorText(text) {
  const value = String(text || "");

  if (value.includes("DATA_EXTRACTION_FAILED")) {
    return "DATA_EXTRACTION_FAILED：未从 PDF 中提取到结构化教育标准表格数据。";
  }

  if (value.includes("ONTOLOGY_VALIDATION_FAILED")) {
    return "ONTOLOGY_VALIDATION_FAILED：records>0 但未生成有效 datatype_properties。";
  }

  return value;
}

async function download() {
  if (!owlFile.value) return;

  const res = await exportOWL(owlFile.value);
  const url = window.URL.createObjectURL(new Blob([res.data]));
  const link = document.createElement("a");

  link.href = url;
  link.download = owlFile.value.split(/[\\/]/).pop() || "ontology.owl";
  link.click();

  window.URL.revokeObjectURL(url);
}

function goSources() {
  router.push("/sources");
}

onBeforeUnmount(() => clearInterval(timer));
</script>

<style scoped>
.page-shell {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}

h1 {
  margin: 0;
}

.path {
  color: #64748b;
  word-break: break-all;
}

.hint {
  color: #475569;
  margin: 8px 0 0;
}

.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

button {
  padding: 10px 14px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  color: white;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.primary {
  background: #2563eb;
}

.success {
  background: #16a34a;
}

.secondary {
  background: #475569;
}

.error {
  color: #b91c1c;
  margin: 12px 0;
  word-break: break-word;
}

.timeout-warning {
  margin-bottom: 14px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fef3c7;
  border: 1px solid #fcd34d;
  color: #92400e;
  font-weight: 700;
}

.progress-panel {
  margin-bottom: 18px;
  text-align: left;
  border: 1px solid #dbeafe;
  background: #f8fbff;
  border-radius: 8px;
  padding: 14px;
}

.progress-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: #1e3a8a;
}

.bar {
  height: 10px;
  background: #dbeafe;
  border-radius: 999px;
  overflow: hidden;
  margin: 10px 0 14px;
}

.bar div {
  height: 100%;
  background: #2563eb;
  transition: width 0.25s ease;
}

.progress-grid,
.summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  text-align: left;
}

.progress-grid div,
.summary div {
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px;
}

.progress-grid strong,
.progress-grid span,
.summary strong,
.summary span {
  display: block;
  word-break: break-all;
}

.progress-grid strong,
.summary strong {
  color: #475569;
  margin-bottom: 4px;
}

.summary {
  margin-bottom: 18px;
}

.warnings {
  margin-top: 12px;
  color: #92400e;
  background: #fef3c7;
  border: 1px solid #fcd34d;
  border-radius: 8px;
  padding: 10px;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.stat {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat strong {
  font-size: 22px;
  color: #0f172a;
}

.stat span {
  color: #64748b;
  font-size: 13px;
}

.panel-grid {
  display: grid;
  grid-template-columns: 1.3fr 0.7fr;
  gap: 14px;
  margin-bottom: 14px;
}

.panel {
  background: white;
  border-radius: 8px;
  padding: 18px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}

.panel h2 {
  margin-top: 0;
}

dl {
  display: grid;
  grid-template-columns: 110px 1fr;
  gap: 10px;
  margin: 0;
}

dt {
  color: #64748b;
}

dd {
  margin: 0;
}

.trace-summary {
  margin-bottom: 14px;
  padding: 16px;
  border-radius: 8px;
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

.preview pre {
  max-height: 52vh;
  overflow: auto;
  background: #0f172a;
  color: #d1d5db;
  padding: 14px;
  border-radius: 6px;
  white-space: pre-wrap;
}

@media (max-width: 860px) {
  .toolbar,
  .panel-grid {
    display: grid;
    grid-template-columns: 1fr;
  }

  .actions {
    justify-content: flex-start;
  }

  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>