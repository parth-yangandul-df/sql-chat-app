import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { connectionApi } from '../api/connectionApi'
import type { ConnectionCreate } from '../types/api'

export function useConnections() {
  return useQuery({
    queryKey: ['connections'],
    queryFn: () => connectionApi.list(),
  })
}

export function useConnection(id: string) {
  return useQuery({
    queryKey: ['connection', id],
    queryFn: () => connectionApi.get(id),
    enabled: !!id,
  })
}

export function useCreateConnection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ConnectionCreate) => connectionApi.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['connections'] }),
  })
}

export function useUpdateConnection(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<ConnectionCreate>) => connectionApi.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['connections'] })
      qc.invalidateQueries({ queryKey: ['connection', id] })
    },
  })
}

export function useDeleteConnection() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => connectionApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['connections'] }),
  })
}

export function useTestConnection() {
  return useMutation({
    mutationFn: (id: string) => connectionApi.test(id),
  })
}

export function useIntrospect() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => connectionApi.introspect(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: ['tables', id] })
    },
  })
}

export function useTables(connectionId: string) {
  return useQuery({
    queryKey: ['tables', connectionId],
    queryFn: () => connectionApi.tables(connectionId),
    enabled: !!connectionId,
  })
}

export function useAvailableTables(connectionId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['availableTables', connectionId],
    queryFn: () => connectionApi.availableTables(connectionId),
    enabled: !!connectionId && enabled,
  })
}
