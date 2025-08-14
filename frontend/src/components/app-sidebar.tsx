import * as React from "react"
import { useContext } from "react"
import { Link, useLocation } from "react-router-dom"
import { FileText, Lightbulb, Settings, PanelLeftIcon, LogOut, Users } from "lucide-react"

import logoUrl from "@/assets/logo.svg"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"
import AuthContext from "@/contexts/AuthContext"

// Items de navigation principale (basés sur router.tsx)
const mainNavItems: Array<{ href: string; label: string; icon: React.ComponentType; tooltip: string }> = [
  { href: '/meetings', label: 'Réunions', icon: FileText, tooltip: 'Réunions' },
  { href: '/prompts', label: 'Gérer les prompts', icon: Lightbulb, tooltip: 'Gérer les prompts' },
]

export function AppSidebar(props: React.ComponentProps<typeof Sidebar>) {
  const location = useLocation()
  const { toggleSidebar } = useSidebar()
  const { user, logout } = useContext(AuthContext) ?? {}

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <div className="group flex items-center px-2 py-2 min-h-10">
          {/* Left: Logo (expanded only) */}
          <Link
            to="/"
            className="flex items-center gap-2"
          >
            <img
              src={logoUrl}
              alt="Logo"
              className="size-6 transition-transform duration-200 group-hover:scale-[1.03]"
            />
          </Link>

          {/* Spacer */}
          <div className="flex-1" />
        </div>
        {/* Search removed from sidebar */}
      </SidebarHeader>
      <SidebarContent>
        {/* Nav principale */}
        <nav className="px-2 py-2">
          <SidebarMenu>
            {mainNavItems.map(({ href, label, icon: Icon, tooltip }) => (
              <SidebarMenuItem key={href}>
                <SidebarMenuButton
                  asChild
                  tooltip={tooltip}
                  isActive={href === '/meetings' ? (location.pathname === '/meetings' || location.pathname === '/' || location.pathname.startsWith('/meetings')) : (location.pathname === href)}
                  className="h-8 px-2 [&>svg]:size-4"
                >
                  <Link to={href}>
                    <Icon />
                    <span>{label}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
            {user?.is_admin && (
              <SidebarMenuItem>
                <SidebarMenuButton
                  asChild
                  tooltip="Administration"
                  isActive={location.pathname === '/admin'}
                  className="h-8 px-2 [&>svg]:size-4"
                >
                  <Link to="/admin">
                    <Users />
                    <span>Administration</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )}
          </SidebarMenu>
        </nav>
      </SidebarContent>

      <SidebarFooter>
        <div className="border-t" />
        <nav className="px-2 py-2">
          <SidebarMenu>
            {/* Réduire */}
            <SidebarMenuItem>
              <SidebarMenuButton onClick={toggleSidebar} tooltip="Réduire" className="h-8 px-2 [&>svg]:size-4">
                <PanelLeftIcon />
                <span className="group-data-[collapsible=icon]:hidden">Réduire</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
            {/* Paramètres */}
            <SidebarMenuItem>
              <SidebarMenuButton asChild tooltip="Paramètres" className="h-8 px-2 [&>svg]:size-4">
                <Link to="/settings" className="flex items-center gap-2">
                  <Settings />
                  <span className="group-data-[collapsible=icon]:hidden">Paramètres</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>

            {/* Profil utilisateur avec menu */}
            <SidebarMenuItem>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <SidebarMenuButton className="h-8 px-2 [&>svg]:size-4" disabled={!user}>
                    <div className="flex items-center gap-2">
                      <Avatar>
                        <AvatarFallback>
                          {user?.email ? user.email.slice(0, 2).toUpperCase() : '??'}
                        </AvatarFallback>
                      </Avatar>
                      <span className="group-data-[collapsible=icon]:hidden">
                        {user?.email ?? ''}
                      </span>
                    </div>
                  </SidebarMenuButton>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="min-w-48">
                  <DropdownMenuItem asChild>
                    <Link to="/settings">Profil</Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={logout}>
                    <LogOut />
                    <span>Se déconnecter</span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </SidebarMenuItem>
          </SidebarMenu>
        </nav>
      </SidebarFooter>
    </Sidebar>
  )
}
