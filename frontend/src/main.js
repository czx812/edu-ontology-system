import { createApp } from "vue";
import App from "./App.vue";
import { createRouter, createWebHistory } from "vue-router";

import Auth from "./views/Auth.vue";
import Dashboard from "./views/Dashboard.vue";
import Result from "./views/Result.vue";
import Profile from "./views/Profile.vue";
import LogManagement from "./views/LogManagement.vue";
import GenerationRecords from "./views/GenerationRecords.vue";
import AdminLogManagement from "./views/AdminLogManagement.vue";
import AdminGenerationRecords from "./views/AdminGenerationRecords.vue";

const routes = [
  { path: "/", component: Auth },
  { path: "/dashboard", component: Dashboard, meta: { requiresAuth: true } },
  { path: "/result", component: Result, meta: { requiresAuth: true } },
  { path: "/profile", component: Profile, meta: { requiresAuth: true } },
  { path: "/logs", component: LogManagement, meta: { requiresAuth: true } },
  { path: "/generations", component: GenerationRecords, meta: { requiresAuth: true } },
  { path: "/admin/logs", component: AdminLogManagement, meta: { requiresAuth: true, requiresAdmin: true } },
  { path: "/admin/generations", component: AdminGenerationRecords, meta: { requiresAuth: true, requiresAdmin: true } },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

function currentUser() {
  try {
    return JSON.parse(localStorage.getItem("user") || "{}");
  } catch (err) {
    return {};
  }
}

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem("token");
  const user = currentUser();
  if (to.meta.requiresAuth && !token) {
    next({ path: "/" });
    return;
  }
  if (to.meta.requiresAdmin && !(user.is_admin || user.role === "admin" || user.username === "admin")) {
    next({ path: "/dashboard" });
    return;
  }
  next();
});

createApp(App).use(router).mount("#app");
