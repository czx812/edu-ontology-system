<template>
  <div class="page">
    <div class="panel">
      <div class="header">
        <div>
          <h1>我的工作台</h1>
          <p>欢迎，{{ userName }}。上传 PDF 后即可进入生成页面，完成本体创建与导出。</p>
        </div>
      </div>

      <div class="content">
        <Upload />
      </div>
    </div>
  </div>
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
.page { min-height: calc(100vh - 58px); padding: 24px; background: #f3f7ff; }
.panel { max-width: 1100px; margin: 0 auto; background: white; border-radius: 12px; padding: 24px; box-shadow: 0 10px 32px rgba(0,0,0,0.08); }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.content { display: grid; gap: 20px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); align-items: start; }
</style>
