import React, { useContext, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import AuthContext from '@/contexts/AuthContext';

interface ProtectedRouteProps {
  children: ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const auth = useContext(AuthContext);
  const location = useLocation();

  // Afficher un état de chargement pendant la vérification du token
  if (auth?.isLoading) {
    return <div>Chargement...</div>;
  }

  // Rediriger uniquement après la fin du chargement si aucun token n'est présent
  if (!auth || !auth.token) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <>{children}</>; // Autoriser l'accès si l'utilisateur est authentifié
};

export default ProtectedRoute;
