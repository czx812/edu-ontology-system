import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 600000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export function registerUser(username, password) {
  return api.post("/auth/register", { username, password });
}

export function loginUser(username, password) {
  return api.post("/auth/login", { username, password });
}

export function getCurrentUser() {
  return api.get("/auth/me");
}

export function uploadPDF(file) {
  const formData = new FormData();
  formData.append("file", file);

  return api.post("/upload", formData);
}

export function generateOntology(filePath) {
  return api.post("/generate", {
    file_path: filePath,
  });
}

export function exportOWL(filePath) {
  return api.get("/export", {
    params: { file_path: filePath },
    responseType: "blob",
  });
}

export function getMyOperations() {
  return api.get("/logs/my-operations");
}

export function getMyGenerations() {
  return api.get("/logs/my-generations");
}

export function getMyQuestions() {
  return api.get("/logs/my-questions");
}

export function getAdminOperationLogs(params = {}) {
  return api.get("/admin/logs/operations", { params });
}

export function getAdminGenerationRecords(params = {}) {
  return api.get("/admin/logs/generations", { params });
}

export function getAdminSystemLogs() {
  return api.get("/admin/logs/system");
}

export function getAdminQuestionRecords(params = {}) {
  return api.get("/admin/logs/questions", { params });
}
