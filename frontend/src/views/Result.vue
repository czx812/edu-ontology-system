<template>
  <section class="page-shell">
    <div class="toolbar">
      <div>
        <h1>本体生成与导出</h1>
        <p class="path">{{ filePath || "请先上传 PDF 文档" }}</p>
      </div>
      <div class="actions">
        <button class="primary" :disabled="loading || !filePath" @click="generate">{{ loading ? "生成中..." : "开始生成" }}</button>
        <button class="success" :disabled="!owlFile" @click="download">导出 OWL</button>
        <button class="secondary" :disabled="!ontology" @click="goSources">检索数据源</button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="stats-row">
      <div class="stat"><strong>{{ stats.classes }}</strong><span>类</span></div>
      <div class="stat"><strong>{{ stats.properties }}</strong><span>属性</span></div>
      <div class="stat"><strong>{{ stats.relations }}</strong><span>关系</span></div>
      <div class="stat"><strong>{{ recordCount }}</strong><span>结构化记录</span></div>
    </div>

    <div class="panel-grid">
      <div class="panel">
        <h2>生成状态</h2>
        <dl>
          <dt>状态</dt><dd>{{ statusText }}</dd>
          <dt>OWL 文件</dt><dd class="path">{{ owlFile || "尚未生成" }}</dd>
          <dt>结构化文件</dt><dd class="path">{{ structuredFile || "尚未生成" }}</dd>
          <dt>生成模式</dt><dd>{{ ontology?.metadata?.generation_mode || ontology?.stats?.generation_mode || "-" }}</dd>
          <dt>LLM</dt><dd>{{ ontology?.metadata?.llm_provider || "-" }} {{ ontology?.metadata?.llm_model || "" }}</dd>
        </dl>
      </div>

      <div class="panel">
        <h2>导出说明</h2>
        <p>生成完成后可下载 OWL 文件，也可以进入数据源检索页面按类、属性、关系和来源文件追踪本体依据。</p>
      </div>
    </div>

    <div class="panel preview" v-if="ontology">
      <h2>本体 JSON 预览</h2>
      <pre>{{ prettyOntology }}</pre>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { generateOntology, exportOWL } from "../api/request";

const route = useRoute();
const router = useRouter();
const filePath = route.query.filePath || localStorage.getItem("lastUploadedPdf") || "";

const ontology = ref(null);
const owlFile = ref("");
const structuredFile = ref("");
const recordCount = ref(0);
const loading = ref(false);
const error = ref("");
const statusText = ref("等待生成");

const stats = computed(() => ({
  classes: ontology.value?.classes?.length || ontology.value?.stats?.classes || 0,
  properties: ontology.value?.properties?.length || ontology.value?.stats?.datatype_properties || 0,
  relations: ontology.value?.relations?.length || ontology.value?.stats?.relations || 0,
}));
const prettyOntology = computed(() => JSON.stringify(ontology.value, null, 2));

async function generate() {
  if (!filePath) {
    error.value = "缺少上传文件，请先返回上传 PDF。";
    return;
  }

  loading.value = true;
  error.value = "";
  ontology.value = null;
  owlFile.value = "";
  structuredFile.value = "";
  recordCount.value = 0;
  statusText.value = "正在生成";

  try {
    const res = await generateOntology(filePath);
    ontology.value = res.data.ontology || {};
    owlFile.value = res.data.owl_file || "";
    structuredFile.value = res.data.structured_file || "";
    recordCount.value = res.data.record_count || 0;
    statusText.value = "生成成功";
    localStorage.setItem("lastOntology", JSON.stringify(ontology.value));
    localStorage.setItem("lastOwlFile", owlFile.value);
    localStorage.setItem("lastStructuredFile", structuredFile.value);
  } catch (err) {
    statusText.value = "生成失败";
    error.value = err.response?.data?.detail || err.message || "生成失败，请查看后端日志。";
  } finally {
    loading.value = false;
  }
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
</script>

<style scoped>
.page-shell { max-width: 1180px; margin: 0 auto; padding: 24px; }
.toolbar { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 16px; }
h1 { margin: 0; }
.path { color: #64748b; word-break: break-all; }
.actions { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
button { padding: 10px 14px; border: none; border-radius: 6px; cursor: pointer; color: white; }
button:disabled { opacity: .6; cursor: not-allowed; }
.primary { background: #2563eb; }
.success { background: #16a34a; }
.secondary { background: #475569; }
.stats-row { display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; margin-bottom: 14px; }
.stat { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; display: flex; flex-direction: column; gap: 4px; }
.stat strong { font-size: 22px; color: #0f172a; }
.stat span { color: #64748b; font-size: 13px; }
.panel-grid { display: grid; grid-template-columns: 1.3fr .7fr; gap: 14px; margin-bottom: 14px; }
.panel { background: white; border-radius: 8px; padding: 18px; box-shadow: 0 8px 24px rgba(15,23,42,0.08); }
.panel h2 { margin-top: 0; }
dl { display: grid; grid-template-columns: 110px 1fr; gap: 10px; margin: 0; }
dt { color: #64748b; }
dd { margin: 0; }
.preview pre { max-height: 52vh; overflow: auto; background: #0f172a; color: #d1d5db; padding: 14px; border-radius: 6px; white-space: pre-wrap; }
.error { color: #b91c1c; }
@media (max-width: 860px) { .toolbar, .panel-grid { display: grid; grid-template-columns: 1fr; } .actions { justify-content: flex-start; } .stats-row { grid-template-columns: repeat(2, 1fr); } }
</style>
