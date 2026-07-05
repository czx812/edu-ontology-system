<template>
  <div class="page">
    <div class="card">
      <h1>🤖 本体生成中心</h1>

      <button class="btn" @click="generate">
        ⚙️ 开始生成
      </button>

      <pre v-if="ontology">{{ ontology }}</pre>

      <button v-if="owlFile" class="btn2" @click="download">
        ⬇ 下载 OWL 文件
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRoute } from "vue-router";
import { generateOntology } from "../api/request";

const route = useRoute();
const filePath = route.query.filePath;

const ontology = ref("");
const owlFile = ref("");

async function generate() {
  const res = await generateOntology(filePath);
  ontology.value = JSON.stringify(res.data.ontology, null, 2);
  owlFile.value = res.data.owl_file;
}

function download() {
  const url = `http://127.0.0.1:8000/export?file_path=${encodeURIComponent(owlFile.value)}`;
  window.open(url, "_blank");
}
</script>

<style scoped>
.page {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(120deg, #f093fb, #f5576c);
}

.card {
  background: white;
  padding: 40px;
  border-radius: 16px;
  width: 500px;
  text-align: center;
  box-shadow: 0 10px 30px rgba(0,0,0,0.2);
}

.btn {
  margin-top: 20px;
  padding: 10px 20px;
  background: #667eea;
  border: none;
  color: white;
  border-radius: 8px;
  cursor: pointer;
}

.btn2 {
  margin-top: 15px;
  padding: 10px 20px;
  background: #00c853;
  border: none;
  color: white;
  border-radius: 8px;
  cursor: pointer;
}

pre {
  background: #f4f4f4;
  padding: 10px;
  margin-top: 20px;
  text-align: left;
  border-radius: 8px;
}
</style>