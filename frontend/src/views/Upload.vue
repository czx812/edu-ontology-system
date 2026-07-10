<template>
  <div class="upload-card">
    <div class="card-head">
      <h2>上传 PDF 文档</h2>
      <span>支持单个或多个 PDF</span>
    </div>

    <label class="drop-zone" :class="{ selected: files.length }">
      <input type="file" accept="application/pdf" multiple :disabled="loading" @change="handleFiles" />
      <strong>{{ files.length ? `已选择 ${files.length} 个 PDF` : "选择或拖入 PDF 文件" }}</strong>
      <small>{{ files.length ? totalSizeLabel : "上传后将进入本体生成流程" }}</small>
    </label>

    <div v-if="files.length" class="file-list">
      <div v-for="item in files" :key="item.name + item.size" class="file-item">
        <span>{{ item.name }}</span>
        <small>{{ formatSize(item.size) }}</small>
      </div>
    </div>

    <div class="options">
      <label>
        <span>生成模式</span>
        <select v-model="mode">
          <option value="rule_draft_llm_enhance">大模型快速增强</option>
          <option value="smoke_llm">仅测试大模型调用</option>
          <option value="rule_only">纯规则备用</option>
        </select>
      </label>

      <label class="check">
        <input v-model="forceRegenerate" type="checkbox" />
        <span>强制重新生成</span>
      </label>

    </div>

    <p class="hint">多文件上传会分别解析每个 PDF，先生成局部本体，再做跨文件对齐、去重和融合。</p>

    <div class="actions">
      <button class="primary" :disabled="loading" @click="upload">
        {{ loading ? "上传中..." : "上传文件" }}
      </button>
      <button class="secondary" :disabled="!filePaths.length" @click="goNext">进入生成页面</button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="uploadedFiles.length" class="success">上传成功：{{ uploadedFiles.map((item) => item.file_name).join("；") }}</p>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import { uploadBatchPDF, uploadPDF } from "../api/request";

const files = ref([]);
const filePaths = ref([]);
const uploadedFiles = ref([]);
const loading = ref(false);
const error = ref("");

const mode = ref("rule_draft_llm_enhance");
const forceRegenerate = ref(false);

const router = useRouter();

const totalSizeLabel = computed(() => formatSize(files.value.reduce((sum, file) => sum + file.size, 0)));

function handleFiles(e) {
  files.value = Array.from(e.target.files || []);
  error.value = "";
  filePaths.value = [];
  uploadedFiles.value = [];
}

function formatSize(size) {
  if (!size) return "0 KB";
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / 1024 / 1024).toFixed(2)} MB`;
}

async function upload() {
  if (!files.value.length) {
    error.value = "请先选择 PDF 文件。";
    return;
  }
  if (files.value.some((file) => file.type && file.type !== "application/pdf")) {
    error.value = "当前仅支持 PDF 文件。";
    return;
  }

  loading.value = true;
  error.value = "";
  filePaths.value = [];
  uploadedFiles.value = [];

  try {
    if (files.value.length === 1) {
      const res = await uploadPDF(files.value[0]);
      filePaths.value = [res.data.file_path];
      uploadedFiles.value = [{ file_path: res.data.file_path, file_name: res.data.file_name || files.value[0].name }];
      localStorage.setItem("lastUploadedPdf", res.data.file_path);
    } else {
      const res = await uploadBatchPDF(files.value);
      filePaths.value = res.data.file_paths || [];
      uploadedFiles.value = (res.data.files || []).map((item) => ({ file_path: item.file_path, file_name: item.filename || item.file_name }));
    }
    localStorage.setItem("lastUploadedPdfs", JSON.stringify(filePaths.value));
    localStorage.setItem("lastUploadedFiles", JSON.stringify(uploadedFiles.value));
    goNext();
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || "上传失败，请确认后端服务已启动。";
  } finally {
    loading.value = false;
  }
}

function goNext() {
  if (!filePaths.value.length) return;
  const query = {
    mode: mode.value,
    forceRegenerate: String(forceRegenerate.value),
  };
  if (filePaths.value.length === 1) query.filePath = filePaths.value[0];
  else query.filePaths = encodeURIComponent(JSON.stringify(filePaths.value));
  router.push({ path: "/result", query });
}
</script>

<style scoped>
.upload-card { display: flex; flex-direction: column; gap: 14px; padding: 20px; border-radius: 8px; background: white; border: 1px solid #e2e8f0; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06); }
.card-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
h2 { margin: 0; }
.card-head span { padding: 4px 8px; border-radius: 999px; background: #e0f2fe; color: #075985; font-size: 12px; }
.drop-zone { min-height: 168px; border: 1px dashed #94a3b8; border-radius: 8px; background: #f8fafc; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; cursor: pointer; text-align: center; padding: 18px; }
.drop-zone.selected { border-color: #2563eb; background: #eff6ff; }
.drop-zone input { display: none; }
.drop-zone strong { color: #0f172a; word-break: break-all; }
.drop-zone small { color: #64748b; }
.file-list { display: grid; gap: 8px; }
.file-item { display: flex; justify-content: space-between; gap: 12px; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 8px; background: #f8fafc; }
.file-item span { word-break: break-all; }
.file-item small { color: #64748b; white-space: nowrap; }
.options { display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); text-align: left; }
.options label { display: grid; gap: 6px; color: #334155; font-weight: 600; }
.options select, .options input[type="number"] { padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 8px; }
.check { display: flex !important; align-items: center; gap: 8px; }
.hint { margin: 0; color: #475569; line-height: 1.5; }
.actions { display: flex; gap: 10px; flex-wrap: wrap; }
button { padding: 10px 14px; border: none; border-radius: 6px; cursor: pointer; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.primary { background: #2563eb; color: white; }
.secondary { background: #16a34a; color: white; }
.success { color: #15803d; word-break: break-all; }
.error { color: #b91c1c; }
</style>
