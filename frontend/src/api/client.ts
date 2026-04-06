import axios from 'axios';

import { clearToken, getToken } from '../utils/auth';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT on every request if present
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Surface real backend error messages; redirect to /login on 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Only redirect on 401 for non-auth endpoints — let LoginPage handle its own 401s
    if (error.response?.status === 401 && !error.config?.url?.includes('/auth/login')) {
      clearToken();
      window.location.href = '/login';
      return Promise.reject(error);
    }
    // FastAPI returns errors in 'detail', not 'error'
    if (error.response?.data?.detail) {
      error.message = error.response.data.detail;
    } else if (error.response?.data?.error) {
      error.message = error.response.data.error;
    }
    return Promise.reject(error);
  },
);

