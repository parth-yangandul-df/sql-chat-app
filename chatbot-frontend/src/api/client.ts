import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
})

// Widget: reads sessionStorage on every request so Angular can set these before any call fires.
// Fallback: if sessionStorage is empty (e.g. timing edge on first render), read ?token= from URL directly.
api.interceptors.request.use((config) => {
  const apiUrl = sessionStorage.getItem('qw_api_url')
  if (apiUrl) config.baseURL = `${apiUrl}/api/v1`
  let token = sessionStorage.getItem('qw_auth_token')
  if (!token) {
    const urlToken = new URLSearchParams(window.location.search).get('token')
    if (urlToken) {
      token = urlToken
      sessionStorage.setItem('qw_auth_token', urlToken)
    }
  }
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (
      error &&
      typeof error === 'object' &&
      'response' in error &&
      error.response &&
      typeof error.response === 'object' &&
      'data' in error.response &&
      error.response.data &&
      typeof error.response.data === 'object' &&
      'error' in error.response.data
    ) {
      const err = error as { message: string; response: { data: { error: string } } }
      err.message = err.response.data.error
    }
    return Promise.reject(error)
  },
)
