import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import * as api from '@/services/api';
import { LoginForm } from '@/components/login-form';

const SignupPage: React.FC = () => {
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  
  const navigate = useNavigate();

  const handleSubmit = async (data: { email: string; password: string; confirmPassword?: string }) => {
    // Vérification de la correspondance des mots de passe
    if (data.password !== data.confirmPassword) {
      setError('Les mots de passe ne correspondent pas');
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      await api.signup(data.email, data.password);
      // Afficher un message de succès
      toast.success("Votre demande d'inscription a été envoyée. Un administrateur l'examinera bientôt.");
      // Succès: rediriger vers la page de connexion
      navigate('/login');
    } catch (err: any) {
      setError(err.message || "Erreur lors de l'inscription");
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