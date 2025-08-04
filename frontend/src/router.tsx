// React import not needed with jsx runtime and verbatimModuleSyntax
import { createBrowserRouter } from 'react-router-dom'
import App from './App'
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import DashboardPage from './pages/DashboardPage'
import ProfilePage from './pages/ProfilePage'
import ProtectedRoute from './routes/ProtectedRoute'
import AnalysisDetailPage from './pages/AnalysisDetailPage'
import DashboardLayout from './layouts/DashboardLayout'

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
            path: 'profile',
            element: <ProfilePage />, // Profil
          },
          {
            path: 'analysis',
            element: <DashboardPage />, // Liste/placeholder
          },
          {
            path: 'analysis/:analysisId',
            element: <AnalysisDetailPage />,
          },
        ],
      },
    ],
  },
])

export default router