// React import not needed with jsx runtime and verbatimModuleSyntax
import { createBrowserRouter } from 'react-router-dom'
import App from './App'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import DashboardPage from './pages/DashboardPage'

import ProtectedRoute from './routes/ProtectedRoute'
import AnalysisDetailPage from './pages/AnalysisDetailPage'
import DashboardLayout from './layouts/DashboardLayout'
import PromptsPage from './pages/PromptsPage'
import HistoryPage from './pages/HistoryPage'
import SettingsPage from './pages/SettingsPage'
import DocumentsPage from './pages/DocumentsPage'

const router = createBrowserRouter([
  {
    path: '/',
    element: <App />, // Shell de base pour routes publiques et parent layout
    children: [
      {
        path: 'login',
        element: <LoginPage />, // Page de connexion
      },
      {
        path: 'register',
        element: <SignupPage />, // Page d'inscription
      },
      {
        // Route parente protégée utilisant le DashboardLayout
        element: (
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        ),
        children: [
          {
            index: true,
            element: <DashboardPage />, // Tableau de bord
          },
          
          {
            path: 'analysis',
            element: <DashboardPage />, // Liste/placeholder
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
            path: 'history',
            element: <HistoryPage />,
          },
          {
            path: 'settings',
            element: <SettingsPage />,
          },
          {
            path: 'documents',
            element: <DocumentsPage />,
          },
        ],
      },
    ],
  },
])

export default router