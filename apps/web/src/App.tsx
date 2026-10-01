import type { ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import SignIn from './pages/SignIn'
import { getTeacher } from './lib/session'

function RequireTeacher({ children }: { children: ReactNode }) {
  const loc = useLocation()
  if (!getTeacher()) return <Navigate to="/signin" replace state={{ from: loc.pathname }} />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/signin" element={<SignIn />} />
      <Route path="*" element={<RequireTeacher><Navigate to="/signin" replace /></RequireTeacher>} />
    </Routes>
  )
}
