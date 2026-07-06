<template>
  <div class="page">
    <div class="card">
      <h1>PDF 上传系统</h1>

      <input type="file" accept="application/pdf" :disabled="loading" @change="handleFile" />

      <button class="btn" :disabled="loading" @click="upload">
        {{ loading ? "上传中..." : "上传文件" }}
      </button>

      <p v-if="error" class="error">{{ error }}</p>

      <p v-if="filePath" class="success">
        上传成功：{{ filePath }}
      </p>

      <button v-if="filePath" class="btn2" @click="goNext">
        去生成本体
      </button>
    </div>
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
.page {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(120deg, #89f7fe, #66a6ff);
}

.card {
  background: white;
  padding: 40px;
  border-radius: 16px;
  width: min(420px, calc(100vw - 32px));
  text-align: center;
  box-shadow: 0 10px 30px rgba(0,0,0,0.2);
}

.btn,
.btn2 {
  margin-top: 20px;
  padding: 10px 20px;
  border: none;
  color: white;
  border-radius: 8px;
  cursor: pointer;
}

.btn {
  background: #4facfe;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.btn2 {
  margin-top: 15px;
  background: #43e97b;
}

.success {
  margin-top: 10px;
  color: green;
  word-break: break-word;
}

.error {
  margin-top: 10px;
  color: #b00020;
  word-break: break-word;
}
</style>
