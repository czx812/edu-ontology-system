<template>
  <div class="upload-card">
    <h2>上传 PDF 文档</h2>
    <input type="file" accept="application/pdf" :disabled="loading" @change="handleFile" />
    <button class="btn" :disabled="loading" @click="upload">
      {{ loading ? "上传中..." : "上传文档" }}
    </button>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="filePath" class="success">上传成功，文件已保存到当前用户空间，可继续生成本体。</p>
    <button v-if="filePath" class="btn2" @click="goNext">进入生成页面</button>
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

async function upload() {
  if (!file.value) {
    error.value = "请先选择一个 PDF 文件。";
    return;
  }

  loading.value = true;
  error.value = "";
  filePath.value = "";

  try {
    const res = await uploadPDF(file.value);
    filePath.value = res.data.file_path;
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || "上传失败，请确认后端服务已启动。";
  } finally {
    loading.value = false;
  }
}

function goNext() {
  router.push({
    path: "/result",
    query: { filePath: filePath.value },
  });
}
</script>

<style scoped>
.upload-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 24px;
  border-radius: 12px;
  background: #f8fbff;
  box-shadow: inset 0 0 0 1px #dce7f5;
}

.btn,
.btn2 {
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  color: white;
  cursor: pointer;
}

.btn { background: #2563eb; }
.btn2 { background: #16a34a; }
.btn:disabled { opacity: 0.7; cursor: not-allowed; }
.success { color: #15803d; }
.error { color: #b91c1c; }
</style>
