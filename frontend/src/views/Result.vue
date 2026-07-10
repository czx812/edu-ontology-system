<template>
  <section class="page-shell">
    <div class="toolbar">
      <div>
        <h1>本体生成与导出</h1>
        <p class="path">{{ isBatch ? `${filePaths.length} 个 PDF` : displayFileName(filePath) || "请先上传 PDF 文件" }}</p>
        <p class="hint">{{ modeLabel }}</p>
      </div>
      <div class="actions">
        <button class="primary" :disabled="loading || (!filePath && !filePaths.length)" @click="generate">{{ loading ? "生成中..." : "开始生成" }}</button>
        <button class="success" :disabled="!owlFile" @click="download">{{ isBatch ? "下载融合 OWL" : "导出 OWL" }}</button>
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
      <div class="stat"><strong>{{ stats.classes }}</strong><span>{{ batchMerged ? "融合类" : isBatch ? "局部类合计" : "类" }}</span></div>
      <div class="stat"><strong>{{ stats.properties }}</strong><span>{{ batchMerged ? "融合属性" : isBatch ? "局部属性合计" : "属性" }}</span></div>
      <div class="stat"><strong>{{ stats.relations }}</strong><span>{{ batchMerged ? "融合关系" : isBatch ? "局部关系合计" : "关系" }}</span></div>
      <div class="stat"><strong>{{ recordCount }}</strong><span>结构化记录</span></div>
    </div>

    <div v-if="batchResult" class="panel batch-panel">
      <h2>批量处理结果</h2>
      <p v-if="batchMerged" class="success">已完成 {{ batchResult.file_count }} 个 PDF 的局部本体生成、跨文件对齐与融合。</p>
      <p v-else class="notice">融合失败或未执行，顶部统计当前显示局部汇总。</p>
      <div class="progress-grid">
        <div><strong>文件数</strong><span>{{ batchResult.file_count }}</span></div>
        <div><strong>状态</strong><span>{{ batchResult.status }}</span></div>
        <div><strong>候选类映射</strong><span>{{ alignmentStats.candidates.classes }}</span></div>
        <div><strong>候选属性映射</strong><span>{{ alignmentStats.candidates.properties }}</span></div>
        <div><strong>候选关系映射</strong><span>{{ alignmentStats.candidates.relations }}</span></div>
      </div>
      <div class="progress-grid summary-grid">
        <div><strong>局部类合计</strong><span>{{ batchStats.local.classes }}</span></div>
        <div><strong>融合类</strong><span>{{ batchStats.merged.classes }}</span></div>
        <div><strong>局部属性合计</strong><span>{{ batchStats.local.properties }}</span></div>
        <div><strong>融合属性</strong><span>{{ batchStats.merged.properties }}</span></div>
        <div><strong>实际合并类 / 属性</strong><span>{{ alignmentStats.applied.classes }} / {{ alignmentStats.applied.properties }}</span></div>
        <div><strong>实际合并关系</strong><span>{{ alignmentStats.applied.relations }}</span></div>
        <div><strong>局部关系合计 / 融合关系</strong><span>{{ batchStats.local.relations }} / {{ batchStats.merged.relations }}</span></div>
      </div>
      <div v-if="batchMerged" class="merged-owl">
        <strong>融合 OWL 已生成</strong>
        <span>文件名：{{ mergedOwlFileName }}</span>
        <button class="success" @click="download">下载融合 OWL</button>
      </div>
      <section v-if="fileResults.length" class="ontology-results">
        <h3>📄 单文件本体生成结果</h3>
        <el-collapse v-model="openOntologyPanels">
          <el-collapse-item v-for="(file, index) in fileResults" :key="file.source_id || `${file.file_name}-${index}`" :name="`file-${index}`">
            <template #title><span class="collapse-title">{{ file.file_name || `文件 ${index + 1}` }}</span></template>
            <div class="provenance">来源 ID：{{ file.source_id || "-" }}　生成时间：{{ formatGeneratedTime(file.generated_time) }}</div>
            <OntologyDetails :ontology="file.ontology" />
          </el-collapse-item>
        </el-collapse>
      </section>
      <section v-if="batchMerged" class="ontology-results merged-result">
        <h3>🔗 多文件融合本体</h3>
        <el-collapse v-model="openOntologyPanels">
          <el-collapse-item name="merged">
            <template #title><span class="collapse-title">最终融合结果</span></template>
            <OntologyDetails :ontology="ontology" />
          </el-collapse-item>
        </el-collapse>
      </section>
      <table>
        <thead><tr><th>文件</th><th>状态</th><th>结构化记录</th><th>类</th><th>属性</th><th>关系</th></tr></thead>
        <tbody>
          <tr v-for="item in batchRows" :key="item.file_path">
            <td>{{ item.original_filename || item.file_name || displayFileName(item.file_path) }}</td>
            <td>{{ item.status }}</td>
            <td>{{ item.record_count || 0 }}</td>
            <td>{{ item.classes || 0 }}</td>
            <td>{{ item.properties || 0 }}</td>
            <td>{{ item.relations || 0 }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="qualityHints.length" class="quality-hints">
        <strong>质量提示</strong>
        <div v-for="hint in qualityHints" :key="hint">{{ hint }}</div>
      </div>
      <div v-if="batchResult.warnings?.length" class="warnings">
        <strong>提示</strong>
        <div v-for="warning in batchResult.warnings" :key="warning">{{ warning }}</div>
      </div>
    </div>

    <div class="panel-grid">
      <div class="panel">
        <h2>生成状态</h2>
        <dl>
          <dt>状态</dt><dd>{{ statusText }}</dd>
          <dt>OWL 文件</dt><dd>{{ owlFile ? displayFileName(owlFile) : "尚未生成" }}</dd>
          <dt>结构化文件</dt><dd>{{ structuredFile || batchResult?.merged_ontology_file ? displayFileName(structuredFile || batchResult?.merged_ontology_file) : "尚未生成" }}</dd>
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
import { computed, defineComponent, h, onBeforeUnmount, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { exportOWL, generateBatchOntology, getGenerationProgress, getGenerationResult, startGeneration } from "../api/request";

const route = useRoute();
const router = useRouter();
const RESULT_STORAGE_KEY = "lastOntologyResult";

function readFilePaths() {
  if (route.query.filePaths) {
    try { return JSON.parse(decodeURIComponent(route.query.filePaths)); } catch (err) { return []; }
  }
  try { return JSON.parse(localStorage.getItem("lastUploadedPdfs") || "[]"); } catch (err) { return []; }
}

function readUploadedFiles() {
  try { return JSON.parse(localStorage.getItem("lastUploadedFiles") || "[]"); } catch (err) { return []; }
}

const filePath = route.query.filePath || localStorage.getItem("lastUploadedPdf") || "";
const filePaths = ref(readFilePaths().filter(Boolean));
const uploadedFiles = ref(readUploadedFiles().filter((item) => item?.file_path));
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
const openOntologyPanels = ref(["merged"]);
let timer = null;

restoreResult();

const modeLabel = computed(() => isBatch.value ? "批量本体构建：局部生成后进行跨文件对齐与融合" : "单文件本体生成");
const batchRows = computed(() => batchResult.value?.local_results || []);
const fileResults = computed(() => batchResult.value?.file_results || batchResult.value?.files || []);
const displayStats = computed(() => countOntologyStats(ontology.value));
const batchMerged = computed(() => Boolean(batchResult.value?.merge_status === "success" && ontology.value));
const batchStats = computed(() => {
  const data = batchResult.value?.batch_stats || {};
  const local = data.local || {};
  const merged = data.merged || {};
  const reduced = data.reduced || {};
  const fallbackLocal = batchRows.value.reduce((total, item) => ({
    classes: total.classes + Number(item.classes || 0),
    properties: total.properties + Number(item.properties || 0),
    relations: total.relations + Number(item.relations || 0),
  }), { classes: 0, properties: 0, relations: 0 });
  const fallbackMerged = {
    classes: displayStats.value.classes,
    properties: displayStats.value.datatype_properties,
    relations: displayStats.value.relations,
  };
  return {
    local: { classes: Number(local.classes ?? fallbackLocal.classes), properties: Number(local.properties ?? fallbackLocal.properties), relations: Number(local.relations ?? fallbackLocal.relations) },
    merged: { classes: Number(merged.classes ?? fallbackMerged.classes), properties: Number(merged.properties ?? fallbackMerged.properties), relations: Number(merged.relations ?? fallbackMerged.relations) },
    reduced: {
      classes: Number(reduced.classes ?? Math.max(0, fallbackLocal.classes - fallbackMerged.classes)),
      properties: Number(reduced.properties ?? Math.max(0, fallbackLocal.properties - fallbackMerged.properties)),
      relations: Number(reduced.relations ?? Math.max(0, fallbackLocal.relations - fallbackMerged.relations)),
    },
  };
});
const alignmentStats = computed(() => {
  const summary = batchResult.value?.alignment_summary || {};
  const candidates = summary.candidate_mappings || {};
  const applied = summary.applied_merges || batchStats.value.reduced;
  const raw = batchResult.value?.alignment_result || {};
  return {
    candidates: {
      classes: Number(candidates.classes ?? raw.class_mappings?.length ?? 0),
      properties: Number(candidates.properties ?? raw.property_mappings?.length ?? 0),
      relations: Number(candidates.relations ?? raw.relation_mappings?.length ?? 0),
    },
    applied: {
      classes: Number(applied.classes ?? 0),
      properties: Number(applied.properties ?? 0),
      relations: Number(applied.relations ?? 0),
    },
  };
});
const stats = computed(() => ({
  classes: isBatch.value && !batchMerged.value ? batchStats.value.local.classes : displayStats.value.classes || progress.value?.stats?.classes || 0,
  properties: isBatch.value && !batchMerged.value ? batchStats.value.local.properties : displayStats.value.datatype_properties || progress.value?.stats?.datatype_properties || 0,
  relations: isBatch.value && !batchMerged.value ? batchStats.value.local.relations : displayStats.value.relations || progress.value?.stats?.relations || 0,
}));
const mergedOwlFileName = computed(() => batchResult.value?.merged_owl_file_name || displayFileName(owlFile.value));
const qualityHints = computed(() => {
  const hints = [...(batchResult.value?.quality_hints || [])];
  const propertyMappings = alignmentStats.value.candidates.properties;
  const appliedProperties = alignmentStats.value.applied.properties;
  const relationMappings = alignmentStats.value.candidates.relations;
  if (propertyMappings >= 20) hints.push(`发现 ${propertyMappings} 条候选属性映射；其中仅 ${appliedProperties} 个按规范化标识实际合并。候选映射不等于融合结果。`);
  if (batchResult.value && relationMappings <= 1) hints.push("候选关系映射较少；请结合引用编号关系检查跨标准关联是否完整。");
  return [...new Set(hints)];
});
const recordCount = computed(() => resultInfo.value?.record_count || batchRows.value.reduce((sum, item) => sum + Number(item.record_count || 0), 0) || progress.value?.stats?.total_records || 0);
const statusText = computed(() => loading.value ? "正在生成" : error.value ? "生成失败" : ontology.value ? "生成成功" : "等待生成");
const prettyOntology = computed(() => ontology.value ? JSON.stringify(ontology.value, null, 2) : "");

const OntologyDetails = defineComponent({
  name: "OntologyDetails",
  props: { ontology: { type: Object, default: () => ({}) } },
  setup(props) {
    const values = (key, fallback = []) => Array.isArray(props.ontology?.[key]) ? props.ontology[key] : fallback;
    const itemName = (item) => {
      return typeof item === "string" ? item : item?.label || item?.name || item?.id || "-";
    };
    const propertyName = (item) => {
      return typeof item === "string" ? item : item?.label || item?.name || item?.id || "-";
    };
    const relationName = (item) => {
      if (typeof item === "string") return item;
      const subject = item?.subject_label || item?.source_label || item?.subject || item?.source || item?.domain || "-";
      const predicate = item?.label || item?.predicate_label || item?.type || item?.predicate || item?.relation || item?.name || item?.id || "-";
      const object = item?.object_label || item?.target_label || item?.object || item?.target || item?.range || "-";
      return `${subject} --${predicate}--> ${object}`;
    };
    const section = (title, items, formatter) => h("div", { class: "ontology-detail-section" }, [
      h("h4", title),
      items.length ? h("ul", items.map((item, index) => h("li", { key: `${title}-${index}` }, formatter(item)))) : h("p", { class: "empty-result" }, "暂无数据"),
    ]);
    return () => h("div", { class: "ontology-detail-grid" }, [
      section("类 (Class)", values("classes"), itemName),
      section("属性 (Property)", values("datatype_properties", values("properties")), propertyName),
      section("关系 (Relation)", [...values("object_properties"), ...values("relations")], relationName),
    ]);
  },
});

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
    const res = await generateBatchOntology(filePaths.value, { ...generationOptions(), enable_merge: true, fileMetadata: uploadedFiles.value });
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
  if (data?.data_type && data.data_type !== "ontology") {
    throw new Error("本体结果接口返回了非 ontology 数据");
  }
  resultInfo.value = data;
  ontology.value = data.ontology || null;
  owlFile.value = data.owl_file || "";
  structuredFile.value = data.structured_file || "";
  persistResult();
}

function setBatchResult(data) {
  if (data?.data_type && data.data_type !== "ontology") {
    throw new Error("本体结果接口返回了非 ontology 数据");
  }
  batchResult.value = data;
  ontology.value = data.merged_ontology || null;
  owlFile.value = data.owl_file || "";
  structuredFile.value = data.merged_ontology_file || "";
  resultInfo.value = data;
  persistResult();
}

function displayFileName(value) {
  return String(value || "").split(/[\\/]/).pop() || "";
}

function formatGeneratedTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function persistResult() {
  if (owlFile.value) localStorage.setItem("lastOwlFile", owlFile.value);
  if (structuredFile.value) localStorage.setItem("lastStructuredFile", structuredFile.value);
  if (ontology.value) localStorage.setItem("lastOntology", JSON.stringify(ontology.value));
  try {
    localStorage.setItem(RESULT_STORAGE_KEY, JSON.stringify({
      version: 1,
      savedAt: new Date().toISOString(),
      filePath,
      filePaths: filePaths.value,
      ontology: ontology.value,
      owlFile: owlFile.value,
      structuredFile: structuredFile.value,
      resultInfo: resultInfo.value,
      batchResult: batchResult.value,
    }));
  } catch (err) {
    // Keep the lightweight ontology cache available for the graph page if the full result is too large.
  }
}

function restoreResult() {
  try {
    const saved = JSON.parse(localStorage.getItem(RESULT_STORAGE_KEY) || "null");
    if (saved?.ontology && typeof saved.ontology === "object") {
      ontology.value = saved.ontology;
      owlFile.value = saved.owlFile || localStorage.getItem("lastOwlFile") || "";
      structuredFile.value = saved.structuredFile || localStorage.getItem("lastStructuredFile") || "";
      resultInfo.value = saved.resultInfo || null;
      batchResult.value = saved.batchResult || null;
      return;
    }

    const lastOntology = JSON.parse(localStorage.getItem("lastOntology") || "null");
    if (lastOntology && typeof lastOntology === "object") {
      ontology.value = lastOntology;
      owlFile.value = localStorage.getItem("lastOwlFile") || "";
      structuredFile.value = localStorage.getItem("lastStructuredFile") || "";
    }
  } catch (err) {
    localStorage.removeItem(RESULT_STORAGE_KEY);
  }
}

function displayError(err) { return err.response?.data?.detail || err.message || "生成失败。"; }
function safeIdentifier(value) {
  return String(value || "").trim().replace(/[^A-Za-z0-9_]+/g, "_").replace(/^_+|_+$/g, "").replace(/_+/g, "_");
}
function classKey(value) {
  return safeIdentifier(value).split("_").filter(Boolean).map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join("").toLowerCase();
}
function propertyKey(value) {
  const text = String(value || "").trim();
  const match = text.match(/\b([A-Z]{2,}[A-Z0-9]*\d{4,})\b/i);
  return (match ? match[1] : safeIdentifier(text)).toLowerCase().slice(0, 100);
}
function countOntologyStats(data) {
  const onto = data && typeof data === "object" ? data : {};
  const classes = new Set();
  const properties = new Set();
  const relations = new Set();

  for (const item of Array.isArray(onto.classes) ? onto.classes : []) {
    const key = classKey(item?.id || item?.name || item?.label);
    if (key) classes.add(key);
  }
  const datatypeItems = Array.isArray(onto.datatype_properties) ? onto.datatype_properties : Array.isArray(onto.properties) ? onto.properties : [];
  for (const item of datatypeItems) {
    const domain = classKey(item?.domain || "EducationResource");
    const name = propertyKey(item?.id || item?.name || item?.label);
    if (name) properties.add(`${domain}|${name}`);
  }
  for (const item of Array.isArray(onto.object_properties) ? onto.object_properties : []) {
    const source = classKey(item?.domain || item?.source || item?.subject);
    const type = propertyKey(item?.id || item?.name || item?.predicate || item?.type);
    const target = classKey(item?.range || item?.target || item?.object);
    if (source && type && target) relations.add(`${source}|${type}|${target}`);
  }
  for (const item of Array.isArray(onto.relations) ? onto.relations : []) {
    const source = classKey(item?.source || item?.subject);
    const type = propertyKey(item?.type || item?.predicate || item?.relation);
    const target = classKey(item?.target || item?.object);
    if (source && type && target) relations.add(`${source}|${type}|${target}`);
  }

  return { classes: classes.size, datatype_properties: properties.size, object_properties: relations.size, relations: relations.size };
}
async function download() {
  if (!owlFile.value) return;
  const downloadKey = batchResult.value?.merged_owl_file_name || owlFile.value;
  const res = await exportOWL(downloadKey);
  const url = window.URL.createObjectURL(new Blob([res.data]));
  const link = document.createElement("a");
  link.href = url;
  link.download = displayFileName(downloadKey) || "ontology.owl";
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
.summary-grid { margin-top: 10px; }.merged-owl { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-top: 12px; padding: 12px; color: #166534; background: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; }.merged-owl button { padding: 7px 10px; }.quality-hints { margin-top: 12px; color: #1e3a8a; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 10px; }.notice { margin: 0 0 12px; color: #92400e; }.warnings { margin-top: 12px; color: #92400e; background: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 10px; }.preview pre { max-height: 52vh; overflow: auto; background: #0f172a; color: #d1d5db; padding: 14px; border-radius: 6px; white-space: pre-wrap; }
.ontology-results { margin-top: 18px; }.ontology-results h3 { margin: 0 0 10px; color: #0f172a; }.merged-result { border-top: 1px solid #e2e8f0; padding-top: 18px; }.collapse-title { font-weight: 600; color: #1e3a8a; }.provenance { margin-bottom: 12px; color: #64748b; font-size: 13px; word-break: break-all; }.ontology-detail-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; padding: 4px 0 10px; }.ontology-detail-section { border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; background: #f8fafc; min-width: 0; }.ontology-detail-section h4 { margin: 0 0 8px; color: #334155; }.ontology-detail-section ul { margin: 0; padding-left: 20px; }.ontology-detail-section li { margin: 4px 0; overflow-wrap: anywhere; }.empty-result { margin: 0; color: #94a3b8; }
@media (max-width: 860px) { .toolbar, .panel-grid, .ontology-detail-grid { display: grid; grid-template-columns: 1fr; } .actions { justify-content: flex-start; } }
</style>


