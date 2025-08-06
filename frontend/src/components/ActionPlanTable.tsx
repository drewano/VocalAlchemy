import type { ActionPlanItem } from '@/types'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'

export interface ActionPlanTableProps {
  actionPlan: ActionPlanItem[] | null
  onItemClick: (interval: { start: number; end: number }) => void
}

function getBadgeVariant(extractionClass: string): 'default' | 'secondary' | 'outline' {
  const key = extractionClass.toLowerCase()
  if (key === 'action') return 'default'
  if (key === 'decision') return 'secondary'
  if (key === 'commitment') return 'outline'
  return 'outline'
}

export function ActionPlanTable({ actionPlan, onItemClick }: ActionPlanTableProps) {
  const hasItems = Array.isArray(actionPlan) && actionPlan.length > 0

  // Group items by topic
  const groupedByTopic: Record<string, ActionPlanItem[]> = (actionPlan || []).reduce((acc, item) => {
    const topic = item.attributes?.topic?.trim() || 'Sans sujet'
    if (!acc[topic]) acc[topic] = []
    acc[topic].push(item)
    return acc
  }, {} as Record<string, ActionPlanItem[]>)

  const topics = Object.keys(groupedByTopic)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Plan d'action</CardTitle>
      </CardHeader>
      <CardContent>
        {!hasItems ? (
          <div className="text-muted-foreground text-sm">Aucun plan d'action n'a été extrait.</div>
        ) : (
          <Accordion type="multiple" className="w-full">
            {topics.map((topic, idx) => (
              <AccordionItem key={topic + idx} value={topic + idx}>
                <AccordionTrigger>{topic}</AccordionTrigger>
                <AccordionContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Type</TableHead>
                        <TableHead>Tâche / Décision</TableHead>
                        <TableHead>Responsable</TableHead>
                        <TableHead>Participants</TableHead>
                        <TableHead>Échéance</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {groupedByTopic[topic].map((item, i) => {
                        const participants = item.attributes?.participants?.length
                          ? item.attributes.participants.join(', ')
                          : 'N/A'
                        const deadline = item.attributes?.deadline?.trim() || 'N/A'
                        const responsible = item.attributes?.responsible?.trim() || 'Non assigné'
                        return (
                          <TableRow
                            key={`${topic}-${i}`}
                            className="cursor-pointer"
                            onClick={() => {
                              const ci = item.char_interval
                              if (ci && typeof ci.start === 'number' && typeof ci.end === 'number') {
                                onItemClick({ start: ci.start, end: ci.end })
                              }
                            }}
                          >
                            <TableCell>
                              <Badge variant={getBadgeVariant(item.extraction_class)}>
                                {item.extraction_class}
                              </Badge>
                            </TableCell>
                            <TableCell>{item.extraction_text}</TableCell>
                            <TableCell>{responsible}</TableCell>
                            <TableCell>{participants}</TableCell>
                            <TableCell>{deadline}</TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        )}
      </CardContent>
    </Card>
  )
}

export default ActionPlanTable
