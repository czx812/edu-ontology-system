<template>
  <div class="page">
    <div class="card">
      <h1>本体生成中心</h1>
      <div class="mode-line">{{ modeLabel }}</div>
      <p class="hint">规则草稿先行，LongCat 只做语义增强，校验通过后导出 OWL。</p>

      <button class="btn" :disabled="loading" @click="generate">{{ loading ? "正在生成..." : "开始生成" }}</button>
      <p v-if="error" class="error">{{ error }}</p>
      <div v-if="timeoutFallback" class="timeout-warning">规则初始本体已生成，大模型轻量增强超时，当前为规则兜底结果。</div>

      <div v-if="progress" class="progress-panel">
        <div class="progress-head">
          <strong>{{ progress.current_step_label }}</strong>
          <span>{{ progress.progress_percent }}%</span>
        </div>
        <div class="bar"><div :style="{ width: `${progress.progress_percent}%` }"></div></div>
        <div class="progress-grid">
          <div><strong>status</strong><span>{{ progress.status }}</span></div>
          <div><strong>stage</strong><span>{{ progress.current_step }}</span></div>
          <div><strong>elapsed</strong><span>{{ progress.elapsed_seconds }} s</span></div>
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

      <div v-if="resultInfo" class="summary">
        <div><strong>结构化文件</strong><span>{{ resultInfo.structured_file || "-" }}</span></div>
        <div><strong>记录数</strong><span>{{ resultInfo.record_count }}</span></div>
        <div><strong>生成状态</strong><span>{{ resultInfo.generation_record?.status }}</span></div>
        <div><strong>耗时</strong><span>{{ resultInfo.generation_record?.duration_ms }} ms</span></div>
        <div v-for="item in statItems" :key="item.key"><strong>{{ item.key }}</strong><span>{{ item.value }}</span></div>
      </div>

      <pre v-if="ontology">{{ ontology }}</pre>
      <button v-if="owlFile" class="btn2" @click="download">下载 OWL 文件</button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from "vue";
import { useRoute } from "vue-router";
import { exportOWL, getGenerationProgress, getGenerationResult, startGeneration } from "../api/request";

const route = useRoute();
const filePath = route.query.filePath;
const mode = computed(() => route.query.mode || "rule_draft_llm_enhance");
const forceRegenerate = computed(() => route.query.forceRegenerate === "true");
const maxGroupRecords = computed(() => Number(route.query.maxGroupRecords || 80));

const ontology = ref("");
const owlFile = ref("");
const resultInfo = ref(null);
const progress = ref(null);
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
  const ontologyData = resultInfo.value?.ontology || {};
  return { ...(ontologyData.stats || {}), ...(ontologyData.metadata || {}) };
});

const statItems = computed(() => [
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
].map((key) => ({ key, value: llmInfo.value[key] ?? "-" })));

const timeoutFallback = computed(() => (
  progress.value?.stats?.generation_mode === "llm_timeout_fallback"
  || llmInfo.value.generation_mode === "llm_timeout_fallback"
));

async function generate() {
  if (!filePath) {
    error.value = "缺少上传文件，请先返回上传 PDF。";
    return;
  }
  loading.value = true;
  error.value = "";
  ontology.value = "";
  owlFile.value = "";
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
        resultInfo.value = result.data;
        ontology.value = JSON.stringify(result.data.ontology, null, 2);
        owlFile.value = result.data.owl_file;
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

function displayError(err) {
  return displayErrorText(err.response?.data?.detail || err.message || "生成失败。");
}

function displayErrorText(text) {
  if (String(text).includes("DATA_EXTRACTION_FAILED")) return "DATA_EXTRACTION_FAILED：未从 PDF 中提取到结构化教育标准表格数据。";
  if (String(text).includes("ONTOLOGY_VALIDATION_FAILED")) return "ONTOLOGY_VALIDATION_FAILED：records>0 但未生成有效 datatype_properties。";
  return text;
}

async function download() {
  if (!owlFile.value) return;
  const res = await exportOWL(owlFile.value);
  const url = window.URL.createObjectURL(new Blob([res.data]));
  const link = document.createElement("a");
  link.href = url;
  link.download = owlFile.value.split("/").pop();
  link.click();
  window.URL.revokeObjectURL(url);
}

onBeforeUnmount(() => clearInterval(timer));
</script>

<style scoped>
.page { min-height: calc(100vh - 58px); display: flex; justify-content: center; align-items: flex-start; background: #eef6ff; padding: 24px; }
.card { background: white; padding: 32px; border-radius: 8px; width: min(1080px, calc(100vw - 32px)); text-align: center; box-shadow: 0 10px 30px rgba(15,23,42,0.14); }
.mode-line { margin-top: -4px; color: #334155; font-weight: 700; }
.hint { color: #475569; margin: 8px 0 0; }
.btn, .btn2 { margin-top: 20px; padding: 10px 20px; border: none; color: white; border-radius: 8px; cursor: pointer; }
.btn { background: #2563eb; }
.btn:disabled { cursor: not-allowed; opacity: 0.7; }
.btn2 { margin-top: 15px; background: #16a34a; }
.error { margin-top: 16px; color: #b00020; word-break: break-word; }
.timeout-warning { margin-top: 14px; padding: 10px 12px; border-radius: 8px; background: #fef3c7; border: 1px solid #fcd34d; color: #92400e; font-weight: 700; }
.progress-panel { margin-top: 18px; text-align: left; border: 1px solid #dbeafe; background: #f8fbff; border-radius: 8px; padding: 14px; }
.progress-head { display: flex; justify-content: space-between; gap: 12px; color: #1e3a8a; }
.bar { height: 10px; background: #dbeafe; border-radius: 999px; overflow: hidden; margin: 10px 0 14px; }
.bar div { height: 100%; background: #2563eb; transition: width 0.25s ease; }
.progress-grid, .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; text-align: left; }
.progress-grid div, .summary div { background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px; }
.summary { margin-top: 18px; }
.progress-grid strong, .progress-grid span, .summary strong, .summary span { display: block; word-break: break-all; }
.progress-grid strong, .summary strong { color: #475569; margin-bottom: 4px; }
.warnings { margin-top: 12px; color: #92400e; background: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 10px; }
pre { max-height: 55vh; overflow: auto; background: #f4f4f4; padding: 10px; margin-top: 20px; text-align: left; border-radius: 8px; }
</style>
