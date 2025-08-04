import React, { useContext, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import AuthContext from '@/contexts/AuthContext';

interface ProtectedRouteProps {
  children: ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const auth = useContext(AuthContext);
  const location = useLocation();

  if (!auth || !auth.token) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <>{children}</>; // Autoriser l'accès si l'utilisateur est authentifié
};

export default ProtectedRoute;
