import React, { useContext } from 'react';
import AuthContext from '@/contexts/AuthContext';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

const ProfileSettings: React.FC = () => {
  const auth = useContext(AuthContext);

  if (!auth) return null;

  const { user, logout } = auth;

  return (
    <div className="w-full max-w-2xl mx-auto">
      <Card>
        <CardHeader>
          <CardTitle>Profil</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <div className="text-sm text-muted-foreground">Email</div>
            <div className="text-base font-medium">{user?.email ?? '—'}</div>
          </div>
          <div className="pt-2">
            <Button variant="destructive" onClick={logout}>Se déconnecter</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ProfileSettings;
export { ProfileSettings };
