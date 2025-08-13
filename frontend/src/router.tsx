// React import not needed with jsx runtime and verbatimModuleSyntax
import * as React from 'react'
import { createBrowserRouter, redirect } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import MeetingsPage from './pages/MeetingsPage'

import ProtectedRoute from './routes/ProtectedRoute'
import AnalysisDetailPage from './pages/AnalysisDetailPage'
import DashboardLayout from './layouts/DashboardLayout'
import PromptsPage from './pages/PromptsPage'
import SettingsPage from './pages/SettingsPage'
import PromptFlowEditorPage from './pages/PromptFlowEditorPage'
import { SetupAdminPage } from './pages/SetupAdminPage'
import * as api from '@/services/api'

const AdminPage = React.lazy(() => import('./pages/AdminPage'))

// Loader for the setup page
const setupLoader = async () => {
  try {
    const { admin_exists } = await api.getSetupStatus()
    // If admin already exists, redirect to login
    if (admin_exists) {
      return redirect('/login')
    }
    // If no admin exists, allow access to setup page
    return null
  } catch (error) {
    console.error('Failed to check setup status:', error)
    // In case of error, allow access to setup page to avoid lockout
    return null
  }
}

// Loader for protected routes
const protectedRoutesLoader = async () => {
  try {
    const { admin_exists } = await api.getSetupStatus()
    // If no admin exists, redirect to setup
    if (!admin_exists) {
      return redirect('/setup')
    }
    // If admin exists, allow access to protected routes
    return null
  } catch (error) {
    console.error('Failed to check setup status:', error)
    // In case of error, redirect to setup to avoid exposing protected content
    return redirect('/setup')
  }
}

const router = createBrowserRouter([
  {
    path: '/setup',
    element: <SetupAdminPage />,
    loader: setupLoader, // Ce loader protège la page de setup elle-même
  },
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/register',
    element: <SignupPage />,
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <DashboardLayout />
      </ProtectedRoute>
    ),
    loader: protectedRoutesLoader, // Ce loader s'applique à TOUTES les routes protégées ci-dessous
    children: [
      {
        index: true,
        element: <MeetingsPage />,
      },
      {
        path: 'meetings',
        element: <MeetingsPage />,
      },
      {
        path: 'analysis/:analysisId',
        element: <AnalysisDetailPage />,
      },
      {
        path: 'prompts',
        element: <PromptsPage />,
      },
      {
        path: 'prompts/new',
        element: <PromptFlowEditorPage />,
      },
      {
        path: 'prompts/:flowId',
        element: <PromptFlowEditorPage />,
      },
      {
        path: 'settings',
        element: <SettingsPage />,
      },
      {
        path: 'admin',
        element: <React.Suspense fallback={<>Chargement...</>}><AdminPage /></React.Suspense>
      },
    ],
  },
])

export default router