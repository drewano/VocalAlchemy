import { useContext } from "react"
import { Bell } from "lucide-react"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import AuthContext from "@/contexts/AuthContext"

export function SiteHeader() {
  const { user } = useContext(AuthContext) ?? {}
  
  const userInitials = user?.email?.charAt(0).toUpperCase() ?? ''
  const avatarSrc = undefined // L'URL de l'avatar n'est pas disponible dans le modèle utilisateur

  return (
    <header className="flex h-(--header-height) shrink-0 items-center gap-2 border-b transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-(--header-height)">
      <div className="flex w-full items-center gap-1 px-4 lg:gap-2 lg:px-6">
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
