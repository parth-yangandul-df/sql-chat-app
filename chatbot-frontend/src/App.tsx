import { Routes, Route, Navigate } from 'react-router-dom'
import { ChatLayout } from '@/components/layout/ChatLayout'
import { ChatQueryPage } from '@/pages/ChatQueryPage'
import { ConnectionsPage } from '@/pages/ConnectionsPage'
import { HistoryPage } from '@/pages/HistoryPage'

export default function App() {
  return (
    <Routes>
      <Route element={<ChatLayout />}>
        <Route index element={<Navigate to="/query" replace />} />
        <Route path="/query" element={<ChatQueryPage />} />
        <Route path="/query/:threadId" element={<ChatQueryPage />} />
        <Route path="/connections" element={<ConnectionsPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="*" element={<Navigate to="/query" replace />} />
      </Route>
    </Routes>
  )
}
