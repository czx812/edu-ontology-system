<template>
  <div class="upload-card">
    <div class="card-head">
      <h2>上传 PDF 文档</h2>
      <span>仅支持 PDF</span>
    </div>

    <label class="drop-zone" :class="{ selected: file }">
      <input type="file" accept="application/pdf" :disabled="loading" @change="handleFile" />
      <strong>{{ file ? file.name : "选择或拖入 PDF 文件" }}</strong>
      <small>{{ file ? formatSize(file.size) : "上传后将进入本体自动生成流程" }}</small>
    </label>

    <div class="actions">
      <button class="primary" :disabled="loading" @click="upload">{{ loading ? "上传中..." : "上传文档" }}</button>
      <button class="secondary" :disabled="!filePath" @click="goNext">进入生成页面</button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="filePath" class="success">上传成功：{{ filePath }}</p>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { uploadPDF } from "../api/request";
import { useRouter } from "vue-router";

const file = ref(null);
const filePath = ref("");
const loading = ref(false);
const error = ref("");
const router = useRouter();

function handleFile(e) {
  file.value = e.target.files[0] || null;
  error.value = "";
  filePath.value = "";
}

function formatSize(size) {
  if (!size) return "0 KB";
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / 1024 / 1024).toFixed(2)} MB`;
}

async function upload() {
  if (!file.value) {
    error.value = "请先选择一个 PDF 文件。";
    return;
  }
  if (file.value.type && file.value.type !== "application/pdf") {
    error.value = "当前仅支持 PDF 文件。";
    return;
  }

  loading.value = true;
  error.value = "";
  filePath.value = "";

  try {
    const res = await uploadPDF(file.value);
    filePath.value = res.data.file_path;
    localStorage.setItem("lastUploadedPdf", filePath.value);
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || "上传失败，请确认后端服务已启动。";
  } finally {
    loading.value = false;
  }
}

function goNext() {
  if (!filePath.value) return;
  router.push({ path: "/result", query: { filePath: filePath.value } });
}
</script>

<style scoped>
.upload-card { display: flex; flex-direction: column; gap: 14px; padding: 20px; border-radius: 8px; background: white; border: 1px solid #e2e8f0; box-shadow: 0 8px 24px rgba(15,23,42,0.06); }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
h2 { margin: 0; }
.card-head span { padding: 4px 8px; border-radius: 999px; background: #e0f2fe; color: #075985; font-size: 12px; }
.drop-zone { min-height: 168px; border: 1px dashed #94a3b8; border-radius: 8px; background: #f8fafc; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; cursor: pointer; text-align: center; padding: 18px; }
.drop-zone.selected { border-color: #2563eb; background: #eff6ff; }
.drop-zone input { display: none; }
.drop-zone strong { color: #0f172a; word-break: break-all; }
.drop-zone small { color: #64748b; }
.actions { display: flex; gap: 10px; flex-wrap: wrap; }
button { padding: 10px 14px; border: none; border-radius: 6px; cursor: pointer; }
button:disabled { opacity: .6; cursor: not-allowed; }
.primary { background: #2563eb; color: white; }
.secondary { background: #16a34a; color: white; }
.success { color: #15803d; word-break: break-all; }
.error { color: #b91c1c; }
</style>
