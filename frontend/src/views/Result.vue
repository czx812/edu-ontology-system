<template>
  <div class="page">
    <div class="card">
      <h1>本体生成中心</h1>
      <button class="btn" :disabled="loading" @click="generate">
        {{ loading ? "正在生成..." : "开始生成" }}
      </button>
      <p v-if="error" class="error">{{ error }}</p>
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

  try {
    const res = await generateOntology(filePath);
    ontology.value = JSON.stringify(res.data.ontology, null, 2);
    owlFile.value = res.data.owl_file;
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
.page { min-height: 100vh; display: flex; justify-content: center; align-items: center; background: linear-gradient(120deg, #f093fb, #f5576c); }
.card { background: white; padding: 40px; border-radius: 16px; width: min(720px, calc(100vw - 32px)); text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
.btn, .btn2 { margin-top: 20px; padding: 10px 20px; border: none; color: white; border-radius: 8px; cursor: pointer; }
.btn { background: #667eea; }
.btn:disabled { cursor: not-allowed; opacity: 0.7; }
.btn2 { margin-top: 15px; background: #00c853; }
.error { margin-top: 16px; color: #b00020; word-break: break-word; }
pre { max-height: 55vh; overflow: auto; background: #f4f4f4; padding: 10px; margin-top: 20px; text-align: left; border-radius: 8px; }
</style>
