import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 600000,
});

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
