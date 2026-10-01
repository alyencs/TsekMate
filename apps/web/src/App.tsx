import type { ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import SignIn from './pages/SignIn'
import Dashboard from './pages/Dashboard'
import Activities from './pages/Activities'
import CreateActivity from './pages/CreateActivity'
import Upload from './pages/Upload'
import Grading from './pages/Grading'
import Queue from './pages/Queue'
import ReviewDetail from './pages/ReviewDetail'
import ClassSummary from './pages/ClassSummary'
import Gradebook from './pages/Gradebook'
import ParentUpdate from './pages/ParentUpdate'
import StudentFeedback from './pages/StudentFeedback'
import Profile from './pages/Profile'
import Settings from './pages/Settings'
import Notifications from './pages/Notifications'
import { getTeacher } from './lib/session'

function RequireTeacher({ children }: { children: ReactNode }) {
  const loc = useLocation()
  if (!getTeacher()) return <Navigate to="/signin" replace state={{ from: loc.pathname }} />
  return <>{children}</>
}

const guard = (el: ReactNode) => <RequireTeacher>{el}</RequireTeacher>

export default function App() {
  return (
    <Routes>
      <Route path="/signin" element={<SignIn />} />
      <Route path="/" element={guard(<Dashboard />)} />
      <Route path="/activities" element={guard(<Activities />)} />
      <Route path="/activities/new" element={guard(<CreateActivity />)} />
      <Route path="/activities/:id/upload" element={guard(<Upload />)} />
      <Route path="/activities/:id/grading" element={guard(<Grading />)} />
      <Route path="/queue" element={guard(<Queue />)} />
      <Route path="/submissions/:id" element={guard(<ReviewDetail />)} />
      <Route path="/submissions/:id/parent-message" element={guard(<ParentUpdate />)} />
      <Route path="/class-summary" element={guard(<ClassSummary />)} />
      <Route path="/gradebook" element={guard(<Gradebook />)} />
      {/* Student view is a teacher-side preview in the prototype (no student logins yet). */}
      <Route path="/feedback/:id" element={guard(<StudentFeedback />)} />
      <Route path="/profile" element={guard(<Profile />)} />
      <Route path="/settings" element={guard(<Settings />)} />
      <Route path="/notifications" element={guard(<Notifications />)} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
