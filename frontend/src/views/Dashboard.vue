<template>
  <div class="page">
    <div class="panel">
      <div class="header">
        <div>
          <h1>我的工作台</h1>
          <p>欢迎，{{ userName }}。上传 PDF 后即可进入生成页面，完成本体创建与导出。</p>
        </div>
        <button class="logout" @click="logout">退出登录</button>
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
    userName.value = res.data.user?.username || "用户";
  } catch (err) {
    localStorage.removeItem("token");
    router.push("/");
  }
});

function logout() {
  localStorage.removeItem("token");
  router.push("/");
}
</script>

<style scoped>
.page { min-height: 100vh; padding: 24px; background: #f3f7ff; }
.panel { max-width: 1100px; margin: 0 auto; background: white; border-radius: 16px; padding: 24px; box-shadow: 0 10px 32px rgba(0,0,0,0.08); }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.logout { padding: 8px 12px; border: none; border-radius: 8px; background: #ef4444; color: white; cursor: pointer; }
.content { display: grid; gap: 20px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); align-items: start; }
</style>
