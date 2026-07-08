<template>
  <div class="upload-card">
    <h2>上传 PDF 文件</h2>
    <input type="file" accept="application/pdf" :disabled="loading" @change="handleFile" />

    <div class="options">
      <label>
        <span>生成模式</span>
        <select v-model="mode">
          <option value="rule_draft_llm_enhance">大模型优先快速生成</option>
          <option value="group_llm">深度全量生成</option>
          <option value="smoke_llm">仅测试大模型调用</option>
          <option value="rule_only">纯规则备用</option>
        </select>
      </label>
      <label class="check">
        <input v-model="forceRegenerate" type="checkbox" />
        <span>强制重新生成，跳过缓存</span>
      </label>
      <label>
        <span>深度模式每组最大 records</span>
        <input v-model.number="maxGroupRecords" type="number" min="20" max="120" />
      </label>
    </div>

    <p class="hint">默认先按结构化 records 生成规则草稿，再调用一次 LongCat 做语义增强。</p>

    <button class="btn" :disabled="loading" @click="upload">{{ loading ? "上传中..." : "上传文件" }}</button>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="filePath" class="success">上传成功，可以进入生成页面。</p>
    <button v-if="filePath" class="btn2" @click="goNext">进入生成页面</button>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { uploadPDF } from "../api/request";

const file = ref(null);
const filePath = ref("");
const loading = ref(false);
const error = ref("");
const mode = ref("rule_draft_llm_enhance");
const forceRegenerate = ref(false);
const maxGroupRecords = ref(80);
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
    query: {
      filePath: filePath.value,
      mode: mode.value,
      forceRegenerate: String(forceRegenerate.value),
      maxGroupRecords: String(maxGroupRecords.value || 80),
    },
  });
}
</script>

<style scoped>
.upload-card { display: flex; flex-direction: column; gap: 12px; padding: 24px; border-radius: 8px; background: #f8fbff; box-shadow: inset 0 0 0 1px #dce7f5; }
.options { display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); text-align: left; }
.options label { display: grid; gap: 6px; color: #334155; font-weight: 600; }
.options select, .options input[type="number"] { padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 8px; }
.check { display: flex !important; align-items: center; gap: 8px; }
.hint { margin: 0; color: #475569; line-height: 1.5; }
.btn, .btn2 { padding: 10px 16px; border: none; border-radius: 8px; color: white; cursor: pointer; }
.btn { background: #2563eb; }
.btn2 { background: #16a34a; }
.btn:disabled { opacity: 0.7; cursor: not-allowed; }
.success { color: #15803d; }
.error { color: #b91c1c; }
</style>
