import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import type { PromptFlow, PromptFlowCreate, PromptFlowUpdate } from '@/types'
import { createPromptFlow, getPromptFlow, updatePromptFlow } from '@/services/promptFlows.api'
import { toast } from 'sonner'
import { DndContext, type DragEndEvent } from '@dnd-kit/core'
import { SortableContext, useSortable, arrayMove, verticalListSortingStrategy } from '@dnd-kit/sortable'

export default function PromptFlowEditorPage() {
  const { flowId } = useParams<{ flowId: string }>()
  const navigate = useNavigate()

  const isEditMode = Boolean(flowId)

  const [name, setName] = useState('')
  const [description, setDescription] = useState<string>('')
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [steps, setSteps] = useState<Array<{ id: string; name: string; content: string }>>([])

  useEffect(() => {
    let isActive = true
    if (!isEditMode) {
      setName('')
      setDescription('')
      setSteps([])
      return
    }
    setIsLoading(true)
    getPromptFlow(flowId!)
      .then((flow: PromptFlow) => {
        if (!isActive) return
        setName(flow.name || '')
        setDescription(flow.description || '')
        const sorted = [...(flow.steps || [])].sort((a, b) => (a.step_order ?? 0) - (b.step_order ?? 0))
        setSteps(sorted.map((s) => ({ id: s.id, name: s.name || '', content: s.content || '' })))
      })
      .catch((err) => {
        toast.error(err?.message || 'Erreur lors du chargement du flux')
      })
      .finally(() => {
        if (!isActive) return
        setIsLoading(false)
      })
    return () => {
      isActive = false
    }
  }, [flowId, isEditMode])

  const handleSave = async () => {
    setIsSaving(true)
    try {
      if (isEditMode) {
        const payload: PromptFlowUpdate = {
          name,
          description,
          steps: steps.map((s, idx) => ({ name: s.name, content: s.content, step_order: idx + 1 })),
        }
        await updatePromptFlow(flowId!, payload)
        toast.success('Flux mis à jour')
      } else {
        const payload: PromptFlowCreate = {
          name,
          description,
          steps: steps.map((s, idx) => ({ name: s.name, content: s.content, step_order: idx + 1 })),
        }
        const created = await createPromptFlow(payload)
        toast.success('Flux créé')
        navigate(`/prompts/${created.id}`)
      }
    } catch (err) {
      const message = (err as { message?: string })?.message || 'Échec de la sauvegarde du flux'
      toast.error(message)
    } finally {
      setIsSaving(false)
    }
  }

  const handleCancel = () => {
    navigate('/prompts')
  }

  const handleAddStep = () => {
    const newId = typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `step_${Date.now()}`
    setSteps((prev) => [...prev, { id: newId, name: '', content: '' }])
  }

  const handleRemoveStep = (id: string) => {
    setSteps((prev) => prev.filter((s) => s.id !== id))
  }

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    setSteps((prev) => {
      const oldIndex = prev.findIndex((s) => s.id === active.id)
      const newIndex = prev.findIndex((s) => s.id === over.id)
      if (oldIndex === -1 || newIndex === -1) return prev
      return arrayMove(prev, oldIndex, newIndex)
    })
  }

  const stepIds = useMemo(() => steps.map((s) => s.id), [steps])

  return (
    <div className="p-4">
      {/* Barre d'actions sticky */}
      <div className="sticky top-0 z-20 -mx-4 px-4 py-4 mb-4 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-b">
        <div className="flex items-center justify-between gap-2">
          <div className="text-lg font-semibold">
            {isEditMode ? 'Modifier un flux de prompts' : 'Nouveau flux de prompts'}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={handleCancel} disabled={isSaving}>Annuler</Button>
            <Button onClick={handleSave} disabled={isSaving || !name.trim()}>{isSaving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Détails</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="flowName" className="text-sm font-medium">Nom</label>
            <Input id="flowName" value={name} onChange={(e) => setName(e.target.value)} disabled={isLoading || isSaving} placeholder="Ex: PV de réunion" />
          </div>

          <div className="space-y-2">
            <label htmlFor="flowDescription" className="text-sm font-medium">Description</label>
            <Textarea id="flowDescription" value={description} onChange={(e) => setDescription(e.target.value)} disabled={isLoading || isSaving} placeholder="Décrivez le but de ce flux" />
          </div>

          <div className="space-y-2">
            <div className="text-sm font-medium">Étapes</div>
            <DndContext onDragEnd={handleDragEnd}>
              <SortableContext items={stepIds} strategy={verticalListSortingStrategy}>
                <div className="space-y-3">
                  {steps.map((step, index) => (
                    <PromptStepCard
                      key={step.id}
                      id={step.id}
                      index={index}
                      name={step.name}
                      content={step.content}
                      allStepKeys={steps.map((s) => s.name).filter(Boolean)}
                      disabled={isSaving || isLoading}
                      onChangeName={(val) => setSteps((prev) => prev.map((s) => (s.id === step.id ? { ...s, name: val } : s)))}
                      onChangeContent={(val) => setSteps((prev) => prev.map((s) => (s.id === step.id ? { ...s, content: val } : s)))}
                      onRemove={() => handleRemoveStep(step.id)}
                    />
                  ))}
                </div>
              </SortableContext>
            </DndContext>

            <div className="pt-2">
              <Button type="button" variant="secondary" onClick={handleAddStep} disabled={isSaving}>
                Ajouter une étape
              </Button>
            </div>
          </div>
        </CardContent>
        <CardFooter className="gap-2 justify-end">
          <Button variant="outline" onClick={handleCancel} disabled={isSaving}>Annuler</Button>
          <Button onClick={handleSave} disabled={isSaving || !name.trim()}>{isSaving ? 'Enregistrement…' : 'Enregistrer'}</Button>
        </CardFooter>
      </Card>
    </div>
  )
}

type PromptStepCardProps = {
  id: string
  index: number
  name: string
  content: string
  allStepKeys: string[]
  disabled?: boolean
  onChangeName: (value: string) => void
  onChangeContent: (value: string) => void
  onRemove: () => void
}

function PromptStepCard({ id, index, name, content, allStepKeys, disabled, onChangeName, onChangeContent, onRemove }: PromptStepCardProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging, setActivatorNodeRef } = useSortable({ id })

  const style: React.CSSProperties = {
    transform: transform ? `translate3d(${Math.round(transform.x)}px, ${Math.round(transform.y)}px, 0)` : undefined,
    transition,
    opacity: isDragging ? 0.85 : 1,
  }

  // Manage caret position for inserting placeholders
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  const insertAtCaret = (text: string) => {
    const value = content || ''
    const token = `{${text}}`
    const el = textareaRef.current as HTMLTextAreaElement | null
    if (el && typeof el.selectionStart === 'number') {
      const start = el.selectionStart as number
      const end = el.selectionEnd as number
      const newVal = value.slice(0, start) + token + value.slice(end)
      onChangeContent(newVal)
      // move caret after token
      setTimeout(() => {
        try {
          el.focus()
          el.selectionStart = el.selectionEnd = start + token.length
        } catch {}
      }, 0)
    } else {
      onChangeContent((value || '') + token)
    }
  }

  const onDropPlaceholder: React.DragEventHandler<HTMLTextAreaElement> = (e) => {
    e.preventDefault()
    const data = e.dataTransfer.getData('text/plain')
    if (data) insertAtCaret(data)
  }

  const onDragOver: React.DragEventHandler<HTMLTextAreaElement> = (e) => {
    e.preventDefault()
  }

  return (
    <div ref={setNodeRef} style={style} className="rounded-md border p-3 bg-background">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-medium">Étape {index + 1}</div>
        <button
          type="button"
          aria-label="Déplacer"
          className="text-xs px-2 py-1 rounded border"
          {...attributes}
          {...listeners}
          ref={setActivatorNodeRef as React.Ref<HTMLButtonElement>}
        >
          ↕
        </button>
      </div>
      <div className="space-y-2">
        <div className="space-y-1">
          <label className="text-xs font-medium">Nom de l'étape (clé de contexte)</label>
          <Input value={name} onChange={(e) => onChangeName(e.target.value)} disabled={disabled} placeholder="ex: intervenants, synthese, actions" />
        </div>
        {/* Palette de placeholders */}
        <PlaceholderPalette
          otherKeys={(allStepKeys || []).filter((k) => k && k !== name)}
          onInsert={insertAtCaret}
        />
        <div className="space-y-1">
          <label className="text-xs font-medium">Contenu du prompt</label>
          <Textarea
            value={content}
            onChange={(e) => onChangeContent(e.target.value)}
            onDrop={onDropPlaceholder}
            onDragOver={onDragOver}
            ref={textareaRef}
            disabled={disabled}
            placeholder="Contenu du prompt, utilisez {transcript}, {analysis_id}, {flow_name} ou les clés d'étapes précédentes. Glissez-déposez des placeholders ci-dessus."
          />
        </div>
        <div className="pt-1 flex justify-end">
          <Button type="button" variant="destructive" onClick={onRemove} disabled={disabled}>
            Supprimer
          </Button>
        </div>
      </div>
    </div>
  )
}

function PlaceholderPalette({ otherKeys, onInsert }: { otherKeys: string[]; onInsert: (token: string) => void }) {
  const baseKeys = ['transcript', 'analysis_id', 'flow_name']
  const keys = [...baseKeys, ...otherKeys]

  const onDragStart: React.DragEventHandler<HTMLButtonElement> = (e) => {
    const token = e.currentTarget.getAttribute('data-token') || ''
    e.dataTransfer.setData('text/plain', token)
  }

  return (
    <div className="flex flex-wrap gap-2 text-xs">
      {keys.map((k) => (
        <button
          key={k}
          type="button"
          className="px-2 py-1 rounded border bg-muted hover:bg-muted/70"
          title={`Insérer {${k}}`}
          draggable
          data-token={k}
          onDragStart={onDragStart}
          onClick={() => onInsert(k)}
        >
          {`{${k}}`}
        </button>
      ))}
    </div>
  )
}


