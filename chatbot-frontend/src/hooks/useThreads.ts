import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { sessionApi } from '../api/sessionApi'

export function useThreads(connectionId?: string) {
  return useQuery({
    queryKey: ['threads', connectionId],
    queryFn: () => sessionApi.list(connectionId),
    enabled: !!connectionId,
    staleTime: 10_000,
  })
}

export function useCreateThread() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { connection_id: string; title?: string }) => sessionApi.create(data),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ['threads', vars.connection_id] })
    },
  })
}

export function useDeleteThread() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id }: { id: string; connection_id: string }) => sessionApi.delete(id),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ['threads', vars.connection_id] })
    },
  })
}

export function useSessionMessages(sessionId?: string) {
  return useQuery({
    queryKey: ['session-messages', sessionId],
    queryFn: () => sessionApi.messages(sessionId!),
    enabled: !!sessionId,
    staleTime: 0,
  })
}
