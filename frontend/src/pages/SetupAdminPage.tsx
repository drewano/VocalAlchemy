import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import * as api from "@/services/api"

export function SetupAdminPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setError(null)

    // Check if passwords match
    if (password !== confirmPassword) {
      setError("Les mots de passe ne correspondent pas")
      return
    }

    setIsLoading(true)
    try {
      await api.createFirstAdmin(email, password)
      toast.success("Compte administrateur créé avec succès")
      navigate("/login")
    } catch (err: any) {
      setError(err?.message || "Échec de la création du compte administrateur")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-2xl font-bold text-center">
            Configuration initiale
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-center mb-6">
            Créer le compte administrateur principal
          </p>
          
          {error && (
            <div className="p-3 bg-red-100 text-red-700 rounded mb-4">
              {error}
            </div>
          )}
          
          <form onSubmit={handleSubmit} className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="admin@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            
            <div className="grid gap-2">
              <Label htmlFor="password">Mot de passe</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            
            <div className="grid gap-2">
              <Label htmlFor="confirmPassword">Confirmer le mot de passe</Label>
              <Input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </div>
            
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? "Création en cours..." : "Créer le compte administrateur"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}