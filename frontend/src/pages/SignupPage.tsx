import React, { useState, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import * as api from '@/services/api';
import AuthContext from '@/contexts/AuthContext';
import { LoginForm } from '@/components/login-form';

const SignupPage: React.FC = () => {
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  
  const authContext = useContext(AuthContext);
  const navigate = useNavigate();

  if (!authContext) {
    throw new Error('SignupPage must be used within an AuthProvider');
  }

  const { signup: authSignup } = authContext;

  const handleSubmit = async (data: { email: string; password: string; confirmPassword?: string }) => {
    // Vérification de la correspondance des mots de passe
    if (data.password !== data.confirmPassword) {
      setError('Les mots de passe ne correspondent pas');
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await api.signup(data.email, data.password);
      // Pour l'instant, on considère que l'ID de l'utilisateur est 1, à remplacer par l'ID réel
      authSignup(response.access_token, { id: '1', email: data.email });
      navigate('/login'); // Rediriger vers la page de connexion
    } catch (err: any) {
      setError(err.response?.data?.detail || "Erreur lors de l'inscription");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
      <LoginForm 
        type="signup" 
        onSubmit={handleSubmit} 
        isLoading={isLoading} 
        error={error} 
      />
    </div>
  );
};

export default SignupPage;