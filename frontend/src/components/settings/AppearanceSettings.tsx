import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { ModeToggle } from '@/components/mode-toggle'

export default function AppearanceSettings() {
  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle>Apparence</CardTitle>
        <CardDescription>Personnalisez l'apparence de l'application, y compris le thème.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between gap-4 py-2">
          <Label htmlFor="theme-toggle">Thème</Label>
          <div id="theme-toggle">
            <ModeToggle />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
