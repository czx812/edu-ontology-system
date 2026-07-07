import { createApp } from "vue";
import App from "./App.vue";
import { createRouter, createWebHistory } from "vue-router";

import Auth from "./views/Auth.vue";
import Dashboard from "./views/Dashboard.vue";
import Result from "./views/Result.vue";

const routes = [
  { path: "/", component: Auth },
  { path: "/dashboard", component: Dashboard, meta: { requiresAuth: true } },
  { path: "/result", component: Result, meta: { requiresAuth: true } },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem("token");
  if (to.meta.requiresAuth && !token) {
    next({ path: "/" });
  } else {
    next();
  }
});

createApp(App).use(router).mount("#app");