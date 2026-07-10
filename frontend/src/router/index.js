import { createRouter, createWebHistory } from "vue-router";
import Auth from "../views/Auth.vue";
import Dashboard from "../views/Dashboard.vue";
import Result from "../views/Result.vue";
import Profile from "../views/Profile.vue";
import LogManagement from "../views/LogManagement.vue";
import GenerationRecords from "../views/GenerationRecords.vue";
import AdminLogManagement from "../views/AdminLogManagement.vue";
import AdminGenerationRecords from "../views/AdminGenerationRecords.vue";
import Sources from "../views/Sources.vue";
import AuditCenter from "../views/AuditCenter.vue";
import UserManagement from "../views/UserManagement.vue";
import Graph from "../views/Graph.vue";

const routes = [
  { path: "/", component: Auth },
  { path: "/dashboard", component: Dashboard, meta: { requiresAuth: true } },
  { path: "/result", component: Result, meta: { requiresAuth: true } },
  { path: "/graph", component: Graph, meta: { requiresAuth: true } },
  { path: "/sources", component: Sources, meta: { requiresAuth: true } },
  { path: "/audit", component: AuditCenter, meta: { requiresAuth: true } },
  { path: "/profile", component: Profile, meta: { requiresAuth: true } },
  { path: "/logs", component: LogManagement, meta: { requiresAuth: true } },
  { path: "/generations", component: GenerationRecords, meta: { requiresAuth: true } },
  { path: "/admin/users", component: UserManagement, meta: { requiresAuth: true, requiresAdmin: true } },
  { path: "/admin/logs", component: AdminLogManagement, meta: { requiresAuth: true, requiresAdmin: true } },
  { path: "/admin/generations", component: AdminGenerationRecords, meta: { requiresAuth: true, requiresAdmin: true } },
  { path: "/:pathMatch(.*)*", redirect: "/dashboard" },
];

const router = createRouter({ history: createWebHistory(), routes });

function currentUser() {
  try { return JSON.parse(localStorage.getItem("user") || "{}"); } catch (err) { return {}; }
}

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem("token");
  const user = currentUser();
  if (to.meta.requiresAuth && !token) return next({ path: "/" });
  if (to.path === "/" && token) return next({ path: "/dashboard" });
  if (to.meta.requiresAdmin && !(user.is_admin || user.role === "admin" || user.username === "admin")) return next({ path: "/dashboard" });
  next();
});

export default router;
