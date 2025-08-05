import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { ProfileSettings } from '@/components/settings/ProfileSettings'
import { AppearanceSettings } from '@/components/settings/AppearanceSettings'

export default function SettingsPage() {
  return (
    <div className="p-4">
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
