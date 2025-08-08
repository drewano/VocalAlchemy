// React import not needed with jsx runtime and verbatimModuleSyntax
import { createBrowserRouter } from 'react-router-dom'
import App from './App'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import MeetingsPage from './pages/MeetingsPage'

import ProtectedRoute from './routes/ProtectedRoute'
import AnalysisDetailPage from './pages/AnalysisDetailPage'
import DashboardLayout from './layouts/DashboardLayout'
import PromptsPage from './pages/PromptsPage'
import SettingsPage from './pages/SettingsPage'
import PromptFlowEditorPage from './pages/PromptFlowEditorPage'

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
            element: <MeetingsPage />, // Page d'accueil: Réunions
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
        ],
      },
    ],
  },
])

export default router