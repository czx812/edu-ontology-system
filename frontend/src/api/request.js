import axios from "axios";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000",
});

// 上传PDF
export function uploadPDF(file) {
  let formData = new FormData();
  formData.append("file", file);

  return api.post("/upload", formData);
}

// 生成本体
export function generateOntology(filePath) {
  return api.post("/generate", {
    file_path: filePath,
  });
}

// 导出OWL
export function exportOWL(filePath) {
  return api.get("/export", {
    params: { file_path: filePath },
  });
}