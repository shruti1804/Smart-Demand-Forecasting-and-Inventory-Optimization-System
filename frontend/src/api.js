import axios from "axios";

// const BASE = "http://127.0.0.1:8000";
const BASE = "https://demandiq-backend.onrender.com";

const authHeader = () => {
  const user = JSON.parse(localStorage.getItem("diq_user") || "null");
  if (!user) return {};
  return { auth: { username: user.username, password: user.password } };
};

export const loginUser = (username, password) =>
  axios.post(`${BASE}/login`, {}, { auth: { username, password } });

export const signupUser = (username, password) =>
  axios.post(`${BASE}/signup`, { username, password });

export const getProducts = () =>
  axios.get(`${BASE}/products`, authHeader());

export const addProduct = (data) =>
  axios.post(`${BASE}/products`, data, authHeader());

export const deleteProduct = (name) =>
  axios.delete(`${BASE}/products/${encodeURIComponent(name)}`, authHeader());

export const logSale = (data) =>
  axios.post(`${BASE}/log-sale`, data, authHeader());

export const getDashboard = (product) =>
  axios.get(`${BASE}/dashboard?product_name=${encodeURIComponent(product)}`, authHeader());

export const uploadCSV = (file) => {
  const form = new FormData();
  form.append("file", file);
  return axios.post(`${BASE}/upload-data`, form, authHeader());
};