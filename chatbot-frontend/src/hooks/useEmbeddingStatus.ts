import { useQuery } from '@tanstack/react-query'
import { embeddingApi } from '../api/embeddingApi'

export function useEmbeddingStatus() {
  return useQuery({
    queryKey: ['embeddingStatus'],
    queryFn: () => embeddingApi.status(),
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return 2000
      const hasActive = data.tasks.some(
        (t) => t.status === 'running' || t.status === 'pending',
      )
      return hasActive ? 2000 : false
    },
  })
}
