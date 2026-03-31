import { Routes, Route } from 'react-router-dom'
import { StandaloneChatPage } from '@/pages/StandaloneChatPage'

export default function App() {
  return (
    <Routes>
      <Route path="*" element={<StandaloneChatPage />} />
    </Routes>
  )
}
