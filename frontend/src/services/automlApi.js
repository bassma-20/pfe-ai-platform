import axios from "axios";

const api = axios.create({
  baseURL: "http://127.0.0.1:8000/api/automl",
});

export const uploadDataset = async (file) => {
  const formData = new FormData();
  formData.append("file", file);

  const res = await api.post("/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
};

export const getEda = async (runId) => {
  const res = await api.get(`/eda/${runId}`);
  return res.data;
};

export const analyzeFeatures = async (payload) => {
  const res = await api.post("/analyze-features", payload);
  return res.data;
};

export const trainModel = async (payload) => {
  const res = await api.post("/train", payload);
  return res.data;
};

export const predictValue = async (payload) => {
  const res = await api.post("/predict", payload);
  return res.data;
};

export const agentRun = async (runId, { targetColumn, problemType, maxSteps = 10 } = {}) => {
  const params = { max_steps: maxSteps };
  if (targetColumn) params.target_column = targetColumn;
  if (problemType)  params.problem_type  = problemType;
  const res = await api.post(`/agent-run/${runId}`, null, { params });
  return res.data;
};