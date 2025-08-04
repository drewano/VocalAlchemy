// React import not needed with jsx runtime and verbatimModuleSyntax
import { createBrowserRouter } from 'react-router-dom';
import App from './App'; // Layout principal
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import DashboardPage from './pages/DashboardPage';
import ProfilePage from './pages/ProfilePage';
import ProtectedRoute from './routes/ProtectedRoute';

const router = createBrowserRouter([
  {
    path: '/',
    element: <App />, // Utilise App comme layout
    children: [
      {
        index: true,
        element: (
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        ), // Page d'accueil - Tableau de bord (protégée)
      },
      {
        path: 'login',
        element: <LoginPage />, // Page de connexion
      },
      {
        path: 'register',
        element: <SignupPage />, // Page d'inscription
      },
      {
        path: 'profile',
        element: (
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        ), // Page de profil (protégée)
      },
      {
        path: 'analysis',
        element: (
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        ), // Page d'analyse (protégée) - Pour l'instant, on utilise le même composant
      },
      // Ajoutez d'autres routes ici
    ],
  },
]);

export default router;
