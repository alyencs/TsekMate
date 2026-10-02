import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { getTeacher } from './lib/session'
import SignIn from './pages/SignIn'
import { Loading } from './components/ui/States'

// Each screen is its own chunk (the charts library loads only with the pages that use it).
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Activities = lazy(() => import('./pages/Activities'))
const CreateActivity = lazy(() => import('./pages/CreateActivity'))
const Upload = lazy(() => import('./pages/Upload'))
const Grading = lazy(() => import('./pages/Grading'))
const Queue = lazy(() => import('./pages/Queue'))
const ReviewDetail = lazy(() => import('./pages/ReviewDetail'))
const ClassSummary = lazy(() => import('./pages/ClassSummary'))
const Gradebook = lazy(() => import('./pages/Gradebook'))
const ParentUpdate = lazy(() => import('./pages/ParentUpdate'))
const StudentFeedback = lazy(() => import('./pages/StudentFeedback'))
const Profile = lazy(() => import('./pages/Profile'))
const Settings = lazy(() => import('./pages/Settings'))

function RequireTeacher({ children }: { children: ReactNode }) {
  const loc = useLocation()
  if (!getTeacher()) return <Navigate to="/signin" replace state={{ from: loc.pathname }} />
  return <>{children}</>
}

const guard = (el: ReactNode) => <RequireTeacher>{el}</RequireTeacher>

export default function App() {
  return (
    <Suspense fallback={<Loading />}>
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
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}
