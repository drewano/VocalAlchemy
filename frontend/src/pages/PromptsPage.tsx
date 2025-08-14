import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Brain, Code2, UsersRound, ClipboardList, MessageSquare } from 'lucide-react'
import { getPromptFlows } from '@/services/promptFlows.api'
import type { PromptFlow } from '@/types'

type LibraryItem = { id: string; name: string; icon: React.ComponentType<{ className?: string }> }

const LIBRARY_ITEMS: LibraryItem[] = [
  { id: 'brainstorm', name: 'Brainstorming', icon: Brain },
  { id: 'code-review', name: 'Code Review Meeting', icon: Code2 },
  { id: 'team-sync', name: 'Réunion d\'équipe', icon: UsersRound },
  { id: 'retrospective', name: 'Rétrospective', icon: ClipboardList },
  { id: 'interview', name: 'Entretien d\'embauche', icon: MessageSquare },
]

export default function PromptsPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [tab, setTab] = useState<'library' | 'mine'>('library')
  const [flows, setFlows] = useState<PromptFlow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (tab !== 'mine') return
    let active = true
    setLoading(true)
    setError(null)
    getPromptFlows()
      .then((data) => {
        if (!active) return
        setFlows(data)
      })
      .catch((e) => setError(e?.message || 'Erreur lors du chargement de vos flux.'))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [tab])

  const filteredLibrary = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return LIBRARY_ITEMS
    return LIBRARY_ITEMS.filter((i) => i.name.toLowerCase().includes(q))
  }, [query])

  const filteredFlows = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return flows
    return flows.filter((f) => f.name.toLowerCase().includes(q))
  }, [query, flows])

  return (
    <div className="mx-auto max-w-6xl p-6">
      {/* Barre d'actions sticky */}
      <div className="sticky top-0 z-20 -mx-6 px-6 py-4 mb-6 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-b">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Rechercher un prompt…"
            className="sm:max-w-sm"
            aria-label="Rechercher"
          />
          <Button onClick={() => navigate('/prompts/new')}>Créer un prompt</Button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <Tabs value={tab} onValueChange={(v) => setTab(v as any)}>
        <TabsList>
          <TabsTrigger value="library">Bibliothèque</TabsTrigger>
          <TabsTrigger value="mine">Mes prompts</TabsTrigger>
        </TabsList>

        <TabsContent value="library" className="mt-4">
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {filteredLibrary.map((item) => {
              const Icon = item.icon
              return (
                <Card key={item.id} className="hover:border-primary/60 transition-colors">
                  <CardHeader className="flex flex-row items-center gap-3">
                    <div className="rounded-md bg-muted p-2"><Icon className="h-5 w-5" /></div>
                    <CardTitle className="text-base">{item.name}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Button variant="outline" onClick={() => navigate('/prompts/new')}>
                      Utiliser ce modèle
                    </Button>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </TabsContent>

        <TabsContent value="mine" className="mt-4">
          {loading ? (
            <div className="text-sm text-muted-foreground">Chargement…</div>
          ) : (
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {filteredFlows.map((flow) => (
                <Card key={flow.id} className="hover:border-primary/60 transition-colors">
                  <CardHeader className="flex flex-row items-center gap-3">
                    <div className="rounded-md bg-muted p-2"><Brain className="h-5 w-5" /></div>
                    <CardTitle className="text-base">{flow.name}</CardTitle>
                  </CardHeader>
                  <CardContent className="flex gap-2">
                    <Button variant="outline" onClick={() => navigate(`/prompts/${flow.id}`)}>Éditer</Button>
                  </CardContent>
                </Card>
              ))}
              {filteredFlows.length === 0 && !loading && (
                <div className="text-sm text-muted-foreground">Aucun flux trouvé.</div>
              )}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
