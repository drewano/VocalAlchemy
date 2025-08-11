import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import ProfileSettings from '@/components/settings/ProfileSettings'
import AppearanceSettings from '@/components/settings/AppearanceSettings'

export default function SettingsPage() {
  return (
    <div className="p-4">
      {/* Barre d'actions sticky */}
      <div className="sticky top-0 z-20 -mx-4 px-4 py-4 mb-4 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-b">
        <div className="text-lg font-semibold">Paramètres</div>
      </div>
      <Tabs defaultValue="profile" className="w-full">
        <TabsList>
          <TabsTrigger value="profile">Profil</TabsTrigger>
          <TabsTrigger value="appearance">Apparence</TabsTrigger>
        </TabsList>
        <div className="mt-4 space-y-4">
          <TabsContent value="profile">
            <ProfileSettings />
          </TabsContent>
          <TabsContent value="appearance">
            <AppearanceSettings />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  )
}
