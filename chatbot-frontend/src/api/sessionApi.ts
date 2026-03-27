import { api } from './client'
import type { ChatSession, ChatSessionMessage } from '../types/api'

export const sessionApi = {
  create: (data: { connection_id: string; title?: string }) =>
    api.post<ChatSession>('/sessions', data).then((r) => r.data),

  list: (connection_id?: string) =>
    api
      .get<ChatSession[]>('/sessions', { params: connection_id ? { connection_id } : undefined })
      .then((r) => r.data),

  get: (id: string) =>
    api.get<ChatSession>(`/sessions/${id}`).then((r) => r.data),

  messages: (session_id: string) =>
    api.get<ChatSessionMessage[]>(`/sessions/${session_id}/messages`).then((r) => r.data),

  updateTitle: (id: string, title: string) =>
    api.patch<{ title: string }>(`/sessions/${id}/title`, { title }).then((r) => r.data),

  delete: (id: string) =>
    api.delete(`/sessions/${id}`).then((r) => r.data),
}
