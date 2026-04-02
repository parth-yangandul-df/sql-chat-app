import { StrictMode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ChatWidget } from '@/components/widget/ChatWidget'
import './index.css'

// One QueryClient shared across all widget instances on the page
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
})

class QueryWiseChat extends HTMLElement {
  private root: Root | null = null

  static get observedAttributes() {
    return ['connection-id']
  }

  connectedCallback() {
    this.root = createRoot(this)
    this.render()
  }

  attributeChangedCallback() {
    this.render()
  }

  disconnectedCallback() {
    this.root?.unmount()
    this.root = null
  }

  private render() {
    const connectionId = this.getAttribute('connection-id') ?? ''
    this.root?.render(
      <StrictMode>
        <QueryClientProvider client={queryClient}>
          <ChatWidget connectionId={connectionId} />
        </QueryClientProvider>
      </StrictMode>,
    )
  }
}

if (!customElements.get('querywise-chat')) {
  customElements.define('querywise-chat', QueryWiseChat)
}
