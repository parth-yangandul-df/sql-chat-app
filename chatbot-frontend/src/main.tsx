import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.tsx'

// ── Token + connection handoff: Angular passes ?token=<jwt>&connection_id=<uuid>
// when opening this page in a new tab. Write both to sessionStorage before React
// mounts so all API calls work correctly from the very first render.
const params = new URLSearchParams(window.location.search)
const tokenParam = params.get('token')
if (tokenParam) {
  sessionStorage.setItem('qw_auth_token', tokenParam)
}
const connectionIdParam = params.get('connection_id')
if (connectionIdParam) {
  sessionStorage.setItem('qw_connection_id', connectionIdParam)
}
if (tokenParam || connectionIdParam) {
  // Clean both params from the URL so they aren't visible / bookmarked
  const cleanUrl = window.location.pathname + window.location.hash
  window.history.replaceState({}, '', cleanUrl)
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
