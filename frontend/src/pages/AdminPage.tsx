import * as React from 'react'
import { useEffect, useState } from 'react'
import { listAdminUsers, approveUser, rejectUser, createAdminUser } from '@/services/api'
import type { AdminUserView } from '@/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'

export default function AdminPage() {
  const [users, setUsers] = useState<AdminUserView[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // États pour la modale de création d'utilisateur
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [newUserEmail, setNewUserEmail] = useState('')
  const [newUserPassword, setNewUserPassword] = useState('')
  const [isCreatingUser, setIsCreatingUser] = useState(false)

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        setIsLoading(true)
        const userData = await listAdminUsers()
        setUsers(userData)
      } catch (err) {
        setError('Erreur lors du chargement des utilisateurs')
        console.error(err)
      } finally {
        setIsLoading(false)
      }
    }

    fetchUsers()
  }, [])

  const handleApprove = async (userId: number) => {
    try {
      await approveUser(userId)
      setUsers(users.map(u => u.id === userId ? { ...u, status: 'APPROVED' } : u))
      toast.success('Utilisateur approuvé avec succès')
    } catch (err) {
      toast.error('Erreur lors de l\'approbation de l\'utilisateur')
      console.error(err)
    }
  }

  const handleReject = async (userId: number) => {
    try {
      await rejectUser(userId)
      setUsers(users.map(u => u.id === userId ? { ...u, status: 'REJECTED' } : u))
      toast.success('Utilisateur rejeté avec succès')
    } catch (err) {
      toast.error('Erreur lors du rejet de l\'utilisateur')
      console.error(err)
    }
  }

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newUserEmail || !newUserPassword) {
      toast.error('Veuillez remplir tous les champs')
      return
    }

    try {
      setIsCreatingUser(true)
      const newUser = await createAdminUser(newUserEmail, newUserPassword)
      
      // Ajouter le nouvel utilisateur à la liste (avec meeting_count = 0 par défaut)
      const newUserView: AdminUserView = {
        ...newUser,
        meeting_count: 0
      }
      setUsers([newUserView, ...users])
      
      // Fermer la modale et réinitialiser les champs
      setIsCreateModalOpen(false)
      setNewUserEmail('')
      setNewUserPassword('')
      
      toast.success('Utilisateur créé avec succès')
    } catch (err) {
      toast.error('Erreur lors de la création de l\'utilisateur')
      console.error(err)
    } finally {
      setIsCreatingUser(false)
    }
  }

  const getStatusBadgeVariant = (status: string) => {
    switch (status) {
      case 'APPROVED':
        return 'default'
      case 'REJECTED':
        return 'destructive'
      default:
        return 'secondary'
    }
  }

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold mb-6">Administration</h1>
        <div className="text-red-500">{error}</div>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Administration</h1>
        <Dialog open={isCreateModalOpen} onOpenChange={setIsCreateModalOpen}>
          <DialogTrigger asChild>
            <Button>Ajouter un utilisateur</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Créer un nouvel utilisateur</DialogTitle>
              <DialogDescription>
                Entrez les informations du nouvel utilisateur ci-dessous.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCreateUser}>
              <div className="grid gap-4 py-4">
                <div className="grid grid-cols-4 items-center gap-4">
                  <label htmlFor="email" className="text-right">
                    Email
                  </label>
                  <Input
                    id="email"
                    type="email"
                    value={newUserEmail}
                    onChange={(e) => setNewUserEmail(e.target.value)}
                    className="col-span-3"
                    placeholder="utilisateur@example.com"
                  />
                </div>
                <div className="grid grid-cols-4 items-center gap-4">
                  <label htmlFor="password" className="text-right">
                    Mot de passe
                  </label>
                  <Input
                    id="password"
                    type="password"
                    value={newUserPassword}
                    onChange={(e) => setNewUserPassword(e.target.value)}
                    className="col-span-3"
                    placeholder="••••••••"
                  />
                </div>
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setIsCreateModalOpen(false)}>
                  Annuler
                </Button>
                <Button type="submit" disabled={isCreatingUser}>
                  {isCreatingUser ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Création...
                    </>
                  ) : (
                    'Créer'
                  )}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
      
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Email</TableHead>
              <TableHead>Statut</TableHead>
              <TableHead>Nombre de réunions</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((user) => (
              <TableRow key={user.id}>
                <TableCell className="font-medium">{user.email}</TableCell>
                <TableCell>
                  <Badge variant={getStatusBadgeVariant(user.status)}>
                    {user.status}
                  </Badge>
                </TableCell>
                <TableCell>{user.meeting_count}</TableCell>
                <TableCell>
                  {user.status === 'PENDING' && (
                    <div className="flex space-x-2">
                      <Button 
                        size="sm" 
                        variant="default"
                        onClick={() => handleApprove(user.id)}
                      >
                        Approuver
                      </Button>
                      <Button 
                        size="sm" 
                        variant="destructive"
                        onClick={() => handleReject(user.id)}
                      >
                        Rejeter
                      </Button>
                    </div>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}