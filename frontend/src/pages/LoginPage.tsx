import React, { useState, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import * as api from '@/services/api';
import AuthContext from '@/contexts/AuthContext';
import { LoginForm } from '@/components/login-form';

const LoginPage: React.FC = () => {
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  
  const authContext = useContext(AuthContext);
  const navigate = useNavigate();

  if (!authContext) {
    throw new Error('LoginPage must be used within an AuthProvider');
  }

  const { login: authLogin } = authContext;

  const handleSubmit = async (data: { email: string; password: string }) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await api.login(data.email, data.password);
      // Utiliser la réponse de l'API: { access_token, user }
      authLogin(response.access_token, response.user);
      navigate('/'); // Rediriger vers le tableau de bord
    } catch (err: any) {
      setError(err.message || 'Erreur de connexion');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
      <LoginForm 
        type="login" 
        onSubmit={handleSubmit} 
        isLoading={isLoading} 
        error={error} 
      />
    </div>
  );
};

export default LoginPage;