import { Outlet, Link, useNavigate } from 'react-router-dom';
import './App.css';
import { ModeToggle } from '@/components/mode-toggle';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator } from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { useContext } from 'react';
import AuthContext from '@/contexts/AuthContext';

function App() {
  const auth = useContext(AuthContext);
  const navigate = useNavigate();

  const handleLogout = () => {
    auth?.logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted/30 text-foreground flex flex-col">
      <header className="w-full border-b border-border/60">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <Link to="/" className="text-2xl font-bold">Audio Analyzer AI</Link>
          <div className="flex items-center gap-2">
            <ModeToggle />
            {auth?.user ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" className="flex items-center gap-2">
                    <Avatar className="h-6 w-6">
                      <AvatarFallback>{auth.user.email?.[0]?.toUpperCase() ?? 'U'}</AvatarFallback>
                    </Avatar>
                    <span className="hidden sm:inline">{auth.user.email}</span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuLabel>Mon compte</DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem asChild>
                    <Link to="/profile">Profil</Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleLogout}>Se déconnecter</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <div className="flex items-center gap-2">
                <Button asChild variant="ghost">
                  <Link to="/login">Connexion</Link>
                </Button>
                <Button asChild>
                  <Link to="/register">Inscription</Link>
                </Button>
              </div>
            )}
          </div>
        </div>
      </header>
      <main className="flex-1 flex flex-col items-center p-4 sm:p-8">
        <Outlet />
      </main>
    </div>
  )
}

export default App
