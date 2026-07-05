import { createApp } from "vue";
import App from "./App.vue";
import { createRouter, createWebHistory } from "vue-router";

import Upload from "./views/Upload.vue";
import Result from "./views/Result.vue";

const routes = [
  { path: "/", component: Upload },
  { path: "/result", component: Result },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

createApp(App).use(router).mount("#app");