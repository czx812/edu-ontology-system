<template>
  <section class="page-shell">
    <div class="toolbar">
      <div>
        <h1>本体生成与导出</h1>
        <p class="path">{{ isBatch ? `${filePaths.length} 个 PDF` : filePath || "请先上传 PDF 文件" }}</p>
        <p class="hint">{{ modeLabel }}</p>
      </div>
      <div class="actions">
        <button class="primary" :disabled="loading || (!filePath && !filePaths.length)" @click="generate">{{ loading ? "生成中..." : "开始生成" }}</button>
        <button class="success" :disabled="!owlFile" @click="download">导出 OWL</button>
        <button class="secondary" :disabled="!ontology" @click="goSources">检索数据源</button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="progress && !isBatch" class="progress-panel">
      <div class="progress-head"><strong>{{ progress.current_step_label || "生成进度" }}</strong><span>{{ progress.progress_percent || 0 }}%</span></div>
      <div class="bar"><div :style="{ width: `${progress.progress_percent || 0}%` }"></div></div>
      <div class="progress-grid">
        <div><strong>status</strong><span>{{ progress.status || "-" }}</span></div>
        <div><strong>stage</strong><span>{{ progress.current_step || "-" }}</span></div>
        <div><strong>records</strong><span>{{ progress.stats?.total_records ?? 0 }}</span></div>
        <div><strong>properties</strong><span>{{ progress.stats?.datatype_properties ?? 0 }}</span></div>
      </div>
    </div>

    <div class="stats-row">
      <div class="stat"><strong>{{ stats.classes }}</strong><span>类</span></div>
      <div class="stat"><strong>{{ stats.properties }}</strong><span>属性</span></div>
      <div class="stat"><strong>{{ stats.relations }}</strong><span>关系</span></div>
      <div class="stat"><strong>{{ recordCount }}</strong><span>结构化记录</span></div>
    </div>

    <div v-if="batchResult" class="panel batch-panel">
      <h2>批量处理结果</h2>
      <div class="progress-grid">
        <div><strong>文件数</strong><span>{{ batchResult.file_count }}</span></div>
        <div><strong>状态</strong><span>{{ batchResult.status }}</span></div>
        <div><strong>class mappings</strong><span>{{ batchResult.alignment_result?.class_mappings?.length || 0 }}</span></div>
        <div><strong>property mappings</strong><span>{{ batchResult.alignment_result?.property_mappings?.length || 0 }}</span></div>
        <div><strong>relation mappings</strong><span>{{ batchResult.alignment_result?.relation_mappings?.length || 0 }}</span></div>
        <div><strong>merged owl</strong><span class="path">{{ owlFile || "-" }}</span></div>
      </div>
      <table>
        <thead><tr><th>文件</th><th>状态</th><th>records</th><th>classes</th><th>properties</th><th>relations</th></tr></thead>
        <tbody>
          <tr v-for="item in batchRows" :key="item.file_path">
            <td class="path">{{ item.file_path }}</td>
            <td>{{ item.status }}</td>
            <td>{{ item.record_count || 0 }}</td>
            <td>{{ item.classes || 0 }}</td>
            <td>{{ item.properties || 0 }}</td>
            <td>{{ item.relations || 0 }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="batchResult.warnings?.length" class="warnings">
        <strong>warnings</strong>
        <div v-for="warning in batchResult.warnings" :key="warning">{{ warning }}</div>
      </div>
    </div>

    <div class="panel-grid">
      <div class="panel">
        <h2>生成状态</h2>
        <dl>
          <dt>状态</dt><dd>{{ statusText }}</dd>
          <dt>OWL 文件</dt><dd class="path">{{ owlFile || "尚未生成" }}</dd>
          <dt>结构化文件</dt><dd class="path">{{ structuredFile || batchResult?.merged_ontology_file || "尚未生成" }}</dd>
          <dt>生成模式</dt><dd>{{ ontology?.metadata?.generation_mode || ontology?.stats?.generation_mode || "-" }}</dd>
        </dl>
      </div>
      <div class="panel">
        <h2>数据源</h2>
        <p>生成完成后可进入数据源检索页面，按 code、label、domain 或 filename 查看来源 PDF、页码、表号和行号。</p>
      </div>
    </div>

    <div class="panel preview" v-if="ontology">
      <h2>本体 JSON 预览</h2>
      <pre>{{ prettyOntology }}</pre>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { exportOWL, generateBatchOntology, getGenerationProgress, getGenerationResult, startGeneration } from "../api/request";

const route = useRoute();
const router = useRouter();

function readFilePaths() {
  if (route.query.filePaths) {
    try { return JSON.parse(decodeURIComponent(route.query.filePaths)); } catch (err) { return []; }
  }
  try { return JSON.parse(localStorage.getItem("lastUploadedPdfs") || "[]"); } catch (err) { return []; }
}

const filePath = route.query.filePath || localStorage.getItem("lastUploadedPdf") || "";
const filePaths = ref(readFilePaths().filter(Boolean));
const isBatch = computed(() => filePaths.value.length > 1);
const mode = computed(() => route.query.mode || "rule_draft_llm_enhance");
const forceRegenerate = computed(() => route.query.forceRegenerate === "true");
const maxGroupRecords = computed(() => Number(route.query.maxGroupRecords || 80));

const ontology = ref(null);
const owlFile = ref("");
const structuredFile = ref("");
const resultInfo = ref(null);
const batchResult = ref(null);
const progress = ref(null);
const loading = ref(false);
const error = ref("");
let timer = null;

const modeLabel = computed(() => isBatch.value ? "批量本体构建：局部生成后进行跨文件对齐与融合" : "单文件本体生成");
const batchRows = computed(() => batchResult.value?.local_results || []);
const stats = computed(() => ({
  classes: ontology.value?.stats?.classes || ontology.value?.classes?.length || progress.value?.stats?.classes || 0,
  properties: ontology.value?.stats?.datatype_properties || ontology.value?.properties?.length || progress.value?.stats?.datatype_properties || 0,
  relations: ontology.value?.stats?.relations || ontology.value?.relations?.length || progress.value?.stats?.relations || 0,
}));
const recordCount = computed(() => resultInfo.value?.record_count || batchRows.value.reduce((sum, item) => sum + Number(item.record_count || 0), 0) || progress.value?.stats?.total_records || 0);
const statusText = computed(() => loading.value ? "正在生成" : error.value ? "生成失败" : ontology.value ? "生成成功" : "等待生成");
const prettyOntology = computed(() => ontology.value ? JSON.stringify(ontology.value, null, 2) : "");

async function generate() {
  if (isBatch.value) return generateBatch();
  if (!filePath) { error.value = "缺少上传文件，请先返回上传 PDF。"; return; }
  resetState();
  try {
    const start = await startGeneration(filePath, generationOptions());
    progress.value = start.data;
    poll(start.data.job_id);
  } catch (err) {
    loading.value = false;
    error.value = displayError(err);
  }
}

async function generateBatch() {
  if (!filePaths.value.length) { error.value = "缺少批量上传文件。"; return; }
  resetState();
  try {
    const res = await generateBatchOntology(filePaths.value, { ...generationOptions(), enable_merge: true });
    setBatchResult(res.data);
  } catch (err) {
    error.value = displayError(err);
  } finally {
    loading.value = false;
  }
}

function generationOptions() {
  return { mode: mode.value, force_regenerate: forceRegenerate.value, max_group_records: maxGroupRecords.value, enable_alignment: true, enable_cache: true, max_generation_seconds: 180, llm_single_call_timeout: 45 };
}

function resetState() {
  loading.value = true; error.value = ""; ontology.value = null; owlFile.value = ""; structuredFile.value = ""; resultInfo.value = null; batchResult.value = null; progress.value = null;
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
        error.value = res.data.error || res.data.message || "生成失败。";
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
  persistResult();
}

function setBatchResult(data) {
  batchResult.value = data;
  ontology.value = data.merged_ontology || null;
  owlFile.value = data.owl_file || "";
  structuredFile.value = data.merged_ontology_file || "";
  resultInfo.value = data;
  persistResult();
}

function persistResult() {
  if (owlFile.value) localStorage.setItem("lastOwlFile", owlFile.value);
  if (structuredFile.value) localStorage.setItem("lastStructuredFile", structuredFile.value);
  if (ontology.value) localStorage.setItem("lastOntology", JSON.stringify(ontology.value));
}

function displayError(err) { return err.response?.data?.detail || err.message || "生成失败。"; }
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
function goSources() { router.push("/sources"); }
onBeforeUnmount(() => clearInterval(timer));
</script>

<style scoped>
.page-shell { max-width: 1180px; margin: 0 auto; padding: 24px; }
.toolbar { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 16px; }
h1 { margin: 0; }.path { color: #64748b; word-break: break-all; }.hint { color: #475569; margin: 8px 0 0; }
.actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
button { padding: 10px 14px; border: none; border-radius: 6px; cursor: pointer; color: white; } button:disabled { opacity: .6; cursor: not-allowed; }
.primary { background: #2563eb; }.success { background: #16a34a; }.secondary { background: #475569; }.error { color: #b91c1c; margin: 12px 0; word-break: break-word; }
.progress-panel, .panel { margin-bottom: 14px; text-align: left; border: 1px solid #e2e8f0; background: white; border-radius: 8px; padding: 16px; box-shadow: 0 8px 24px rgba(15, 23, 42, .08); }
.progress-head { display: flex; justify-content: space-between; color: #1e3a8a; }.bar { height: 10px; background: #dbeafe; border-radius: 999px; overflow: hidden; margin: 10px 0 14px; }.bar div { height: 100%; background: #2563eb; }
.progress-grid, .stats-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; }.progress-grid div, .stat { background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px; }.progress-grid strong, .progress-grid span { display: block; word-break: break-all; }.stat strong { display: block; font-size: 22px; color: #0f172a; }.stat span { color: #64748b; font-size: 13px; }
.stats-row { margin-bottom: 14px; }.panel-grid { display: grid; grid-template-columns: 1.3fr .7fr; gap: 14px; margin-bottom: 14px; } .panel h2 { margin-top: 0; } dl { display: grid; grid-template-columns: 110px 1fr; gap: 10px; margin: 0; } dt { color: #64748b; } dd { margin: 0; }
table { width: 100%; border-collapse: collapse; margin-top: 12px; } th, td { border-bottom: 1px solid #e5e7eb; padding: 9px; text-align: left; vertical-align: top; }
.warnings { margin-top: 12px; color: #92400e; background: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 10px; }.preview pre { max-height: 52vh; overflow: auto; background: #0f172a; color: #d1d5db; padding: 14px; border-radius: 6px; white-space: pre-wrap; }
@media (max-width: 860px) { .toolbar, .panel-grid { display: grid; grid-template-columns: 1fr; } .actions { justify-content: flex-start; } }
</style>
