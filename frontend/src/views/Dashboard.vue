<template>
  <section class="page-shell">
    <div class="hero">
      <div>
        <h1>普通用户工作台</h1>
        <p>欢迎，{{ userName }}。上传教育管理标准 PDF，系统将自动抽取数据项、构建本体并生成可导出的 OWL 文件。</p>
      </div>
      <div class="hero-meta">
        <span>PDF 输入</span>
        <strong>本体生成 / 数据源检索 / 安全审计</strong>
      </div>
    </div>

    <div class="workflow">
      <div class="step active"><strong>1</strong><span>上传 PDF 文档</span></div>
      <div class="step"><strong>2</strong><span>自动解析并生成本体</span></div>
      <div class="step"><strong>3</strong><span>导出 OWL 与检索来源</span></div>
    </div>

    <div class="content-grid">
      <Upload />
      <aside class="info-panel">
        <h2>可用能力</h2>
        <ul>
          <li>普通用户注册登录后进入独立工作台。</li>
          <li>上传 PDF 后自动调用后端工作流生成本体文件。</li>
          <li>生成结果可下载 OWL，并进入数据源检索追溯来源。</li>
          <li>审计中心记录生成、提问和操作日志。</li>
        </ul>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import Upload from "./Upload.vue";
import { getCurrentUser } from "../api/request";

const router = useRouter();
const userName = ref("用户");

onMounted(async () => {
  try {
    const res = await getCurrentUser();
    const user = res.data.user || {};
    userName.value = user.username || "用户";
    localStorage.setItem("user", JSON.stringify(user));
  } catch (err) {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.push("/");
  }
});
</script>

<style scoped>
.page-shell { max-width: 1180px; margin: 0 auto; padding: 24px; }
.hero { display: flex; justify-content: space-between; align-items: flex-end; gap: 18px; padding: 22px; border-radius: 8px; background: #ffffff; border: 1px solid #e2e8f0; box-shadow: 0 8px 24px rgba(15,23,42,0.06); margin-bottom: 16px; }
.hero h1 { margin: 0; font-size: 28px; }
.hero p { margin: 8px 0 0; color: #64748b; max-width: 720px; line-height: 1.7; }
.hero-meta { min-width: 240px; padding: 14px; border: 1px solid #dbeafe; border-radius: 8px; background: #f8fbff; display: flex; flex-direction: column; gap: 6px; }
.hero-meta span { color: #64748b; font-size: 13px; }
.workflow { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 16px; }
.step { min-height: 58px; display: flex; align-items: center; gap: 10px; padding: 12px; background: #e2e8f0; border-radius: 8px; color: #334155; }
.step strong { width: 28px; height: 28px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; background: white; color: #1d4ed8; }
.step.active { background: #dbeafe; }
.content-grid { display: grid; grid-template-columns: minmax(320px, 1fr) 340px; gap: 16px; align-items: start; }
.info-panel { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; box-shadow: 0 8px 24px rgba(15,23,42,0.06); }
.info-panel h2 { margin-top: 0; }
ul { margin: 0; padding-left: 20px; color: #475569; line-height: 1.9; }
@media (max-width: 900px) { .hero, .content-grid { display: grid; grid-template-columns: 1fr; } .workflow { grid-template-columns: 1fr; } }
</style>
