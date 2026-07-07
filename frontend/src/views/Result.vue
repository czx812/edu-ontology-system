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
      <button v-if="owlFile" class="btn2" @click="download">下载 OWL 文件</button>
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
  owlFile.value = "";
  resultInfo.value = null;

  try {
    const res = await generateOntology(filePath);
    ontology.value = JSON.stringify(res.data.ontology, null, 2);
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
pre { max-height: 55vh; overflow: auto; background: #f4f4f4; padding: 10px; margin-top: 20px; text-align: left; border-radius: 8px; }
</style>
