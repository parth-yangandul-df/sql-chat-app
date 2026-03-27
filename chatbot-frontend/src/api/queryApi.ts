import { api } from './client'
import type { QueryResult, QueryHistory } from '../types/api'

export interface ConversationTurn {
  role: 'user' | 'assistant'
  content: string
}

export const queryApi = {
  execute: (data: {
    connection_id: string
    question: string
    session_id?: string
    conversation_history?: ConversationTurn[]
  }) => api.post<QueryResult>('/query', data).then((r) => r.data),

  history: (params?: { connection_id?: string; limit?: number; offset?: number }) =>
    api.get<QueryHistory[]>('/query-history', { params }).then((r) => r.data),

  toggleFavorite: (id: string) =>
    api.patch<{ is_favorite: boolean }>(`/query-history/${id}/favorite`).then((r) => r.data),
}
