<template>
  <div class="page">
    <div class="card">
      <h1>📄 PDF 上传系统</h1>

      <input type="file" @change="handleFile" />

      <button class="btn" @click="upload">
        上传文件
      </button>

      <p v-if="filePath" class="success">
        ✔ 上传成功：{{ filePath }}
      </p>

      <button v-if="filePath" class="btn2" @click="goNext">
        🚀 去生成本体
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
const router = useRouter();

function handleFile(e) {
  file.value = e.target.files[0];
}

async function upload() {
  const res = await uploadPDF(file.value);
  filePath.value = res.data.file_path;
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
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(120deg, #89f7fe, #66a6ff);
}

.card {
  background: white;
  padding: 40px;
  border-radius: 16px;
  width: 400px;
  text-align: center;
  box-shadow: 0 10px 30px rgba(0,0,0,0.2);
}

.btn {
  margin-top: 20px;
  padding: 10px 20px;
  background: #4facfe;
  border: none;
  color: white;
  border-radius: 8px;
  cursor: pointer;
}

.btn2 {
  margin-top: 15px;
  padding: 10px 20px;
  background: #43e97b;
  border: none;
  color: white;
  border-radius: 8px;
  cursor: pointer;
}

.success {
  margin-top: 10px;
  color: green;
}
</style>