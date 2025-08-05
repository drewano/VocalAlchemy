import React, { useEffect, useState } from 'react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { getUserPrompts, createUserPrompt, updateUserPrompt, deleteUserPrompt } from '@/services/prompts.api'
import type { UserPrompt } from '@/types'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'

function truncate(text: string, max = 120) {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '…' : text
}

export default function PromptsPage() {
  const [prompts, setPrompts] = useState<UserPrompt[]>([])
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  const [open, setOpen] = useState<boolean>(false)
  const [editing, setEditing] = useState<UserPrompt | null>(null)
  const [form, setForm] = useState<{ name: string; content: string }>({ name: '', content: '' })
  const [saving, setSaving] = useState<boolean>(false)

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getUserPrompts()
      setPrompts(data)
    } catch (e: any) {
      setError(e?.message || 'Erreur lors du chargement des prompts.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const onCreateClick = () => {
    setEditing(null)
    setForm({ name: '', content: '' })
    setOpen(true)
  }

  const onEditClick = (p: UserPrompt) => {
    setEditing(p)
    setForm({ name: p.name, content: p.content })
    setOpen(true)
  }

  const onDelete = async (id: number) => {
    if (!confirm('Supprimer ce prompt ?')) return
    try {
      await deleteUserPrompt(id)
      await fetchData()
    } catch (e: any) {
      setError(e?.message || 'Suppression échouée.')
    }
  }

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      if (editing) {
        await updateUserPrompt(editing.id, form)
      } else {
        await createUserPrompt(form)
      }
      setOpen(false)
      await fetchData()
    } catch (e: any) {
      setError(e?.message || 'Enregistrement échoué.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl p-6">
      <Card>
        <CardHeader className="flex items-center justify-between gap-4 sm:flex-row">
          <div>
            <CardTitle className="text-xl">Prompts personnalisés</CardTitle>
            <CardDescription>Créez et gérez vos prompts pour l'analyse.</CardDescription>
          </div>
          <Button onClick={onCreateClick}>Créer un nouveau prompt</Button>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="mb-4 rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}

          {loading ? (
            <div className="text-sm text-muted-foreground">Chargement…</div>
          ) : prompts.length === 0 ? (
            <div className="text-sm text-muted-foreground">Aucun prompt trouvé.</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nom</TableHead>
                  <TableHead>Contenu (tronqué)</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {prompts.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">{p.name}</TableCell>
                    <TableCell className="max-w-[520px]">{truncate(p.content)}</TableCell>
                    <TableCell className="space-x-2">
                      <Button variant="outline" size="sm" onClick={() => onEditClick(p)}>
                        Modifier
                      </Button>
                      <Button variant="destructive" size="sm" onClick={() => onDelete(p.id)}>
                        Supprimer
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? 'Modifier le prompt' : 'Nouveau prompt'}</DialogTitle>
            <DialogDescription>
              Définissez un nom et le contenu de votre prompt. Le nom sera utilisé pour la sélection rapide.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Nom</label>
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Nom du prompt"
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Contenu</label>
              <Textarea
                value={form.content}
                onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))}
                placeholder="Le contenu complet du prompt"
                rows={8}
                required
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setOpen(false)} disabled={saving}>
                Annuler
              </Button>
              <Button type="submit" disabled={saving}>
                {saving ? 'Enregistrement…' : 'Enregistrer'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
