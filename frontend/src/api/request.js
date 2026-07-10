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


export function uploadBatchPDF(files) {
  const formData = new FormData();
  Array.from(files || []).forEach((file) => formData.append("files", file));
  return api.post("/upload/batch", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}
export function generateOntology(filePath, options = {}) {
  return api.post("/generate", {
    file_path: filePath,
    mode: options.mode || "rule_draft_llm_enhance",
    force_regenerate: Boolean(options.force_regenerate),
    max_group_records: Number(options.max_group_records || 80),
    enable_review: Boolean(options.enable_review),
    enable_alignment: options.enable_alignment !== false,
    enable_deep_alignment: Boolean(options.enable_deep_alignment),
    enable_global_merge: Boolean(options.enable_global_merge),
    enable_cache: options.enable_cache !== false,
    max_generation_seconds: Number(options.max_generation_seconds || 180),
    llm_single_call_timeout: Number(options.llm_single_call_timeout || 45),
  });
}

export function startGeneration(filePath, options = {}) {
  return api.post("/generate/start", {
    file_path: filePath,
    mode: options.mode || "rule_draft_llm_enhance",
    force_regenerate: Boolean(options.force_regenerate),
    max_group_records: Number(options.max_group_records || 80),
    enable_review: Boolean(options.enable_review),
    enable_alignment: options.enable_alignment !== false,
    enable_deep_alignment: Boolean(options.enable_deep_alignment),
    enable_global_merge: Boolean(options.enable_global_merge),
    enable_cache: options.enable_cache !== false,
    max_generation_seconds: Number(options.max_generation_seconds || 180),
    llm_single_call_timeout: Number(options.llm_single_call_timeout || 45),
  });
}

export function getGenerationProgress(jobId) {
  return api.get(`/generate/progress/${jobId}`);
}

export function getGenerationResult(jobId) {
  return api.get(`/generate/result/${jobId}`);
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

export function searchDataSources(params = {}) {
  return api.get("/sources/search", { params });
}

export function getAdminUsers() {
  return api.get("/admin/users");
}

export function generateBatchOntology(filePaths, options = {}) {
  return api.post("/generate/batch", {
    file_paths: filePaths,
    file_metadata: Array.isArray(options.fileMetadata) ? options.fileMetadata : [],
    mode: options.mode || "rule_draft_llm_enhance",
    force_regenerate: Boolean(options.force_regenerate),
    max_group_records: Number(options.max_group_records || 80),
    enable_review: Boolean(options.enable_review),
    enable_alignment: options.enable_alignment !== false,
    enable_deep_alignment: Boolean(options.enable_deep_alignment),
    enable_global_merge: Boolean(options.enable_global_merge),
    enable_cache: options.enable_cache !== false,
    enable_merge: options.enable_merge !== false,
    max_generation_seconds: Number(options.max_generation_seconds || 180),
    llm_single_call_timeout: Number(options.llm_single_call_timeout || 45),
  });
}

