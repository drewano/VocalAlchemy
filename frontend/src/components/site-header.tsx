import { SidebarTrigger } from "@/components/ui/sidebar"
import { Bell } from "lucide-react"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"

export function SiteHeader() {
  // TODO: brancher l'avatar utilisateur via le contexte d'authentification si disponible
  const userInitials = "AA"
  const avatarSrc = undefined // Remplacer par l'URL de l'avatar utilisateur si disponible

  return (
    <header className="flex h-(--header-height) shrink-0 items-center gap-2 border-b transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-(--header-height)">
      <div className="flex w-full items-center gap-1 px-4 lg:gap-2 lg:px-6">
        <SidebarTrigger className="-ml-1" />
        <h1 className="text-2xl font-semibold">Tableau de bord</h1>
        <div className="ml-auto flex items-center">
          <Bell className="text-gray-500 mr-4" />
          <Avatar>
            <AvatarImage src={avatarSrc} alt="User avatar" />
            <AvatarFallback>{userInitials}</AvatarFallback>
          </Avatar>
        </div>
      </div>
    </header>
  )
}
