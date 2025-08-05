import * as React from "react"
import { Link, useLocation } from "react-router-dom"
import { LayoutDashboard, History, FileText, Lightbulb, Settings, User } from "lucide-react"
import { useAnalysisHistory } from "@/hooks/useAnalysisHistory"
import { SearchForm } from "@/components/search-form"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarGroupContent,
  SidebarMenuSkeleton,
} from "@/components/ui/sidebar"

function truncate(text: string, max = 40) {
  if (!text) return ""
  return text.length > max ? text.slice(0, max) + "…" : text
}

export function AppSidebar({ onSearchChange, ...props }: React.ComponentProps<typeof Sidebar> & { onSearchChange?: (term: string) => void }) {
  const { history, isLoading } = useAnalysisHistory()
  const location = useLocation()

  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild className="data-[slot=sidebar-menu-button]:!p-1.5">
              <Link to="/">
                <span className="text-base font-semibold">Audio Analyzer AI</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
        <SearchForm className="px-0" onSearchChange={onSearchChange} />
      </SidebarHeader>
      <SidebarContent>
        {/* Nav principale */}
        <nav className="px-2 py-2">
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton asChild className={location.pathname === '/' ? 'bg-gray-100' : undefined}>
                <Link to="/">
                  <LayoutDashboard />
                  <span>Tableau de bord</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton asChild>
                <Link to="/history">
                  <History />
                  <span>Historique</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton asChild>
                <Link to="/documents">
                  <FileText />
                  <span>Documents</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton asChild>
                <Link to="/prompts">
                  <Lightbulb />
                  <span>Gérer les prompts</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </nav>

        <div className="border-t my-2" />

        {/* Historique listé (conservé) */}
        <SidebarGroup>
          <SidebarGroupLabel>Historique</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {isLoading ? (
                Array.from({ length: 4 }).map((_, idx) => (
                  <SidebarMenuSkeleton key={idx} />
                ))
              ) : (
                history.map((item) => (
                  <SidebarMenuItem key={item.id}>
                    <SidebarMenuButton asChild>
                      <Link to={`/analysis/${item.id}`} title={item.filename}>
                        <span>{truncate(item.filename)}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <div className="border-t" />
        <nav className="px-2 py-2">
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton asChild>
                <Link to="/settings">
                  <Settings />
                  <span>Paramètres</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton asChild>
                <Link to="/profile">
                  <User />
                  <span>Profil</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </nav>
      </SidebarFooter>
    </Sidebar>
  )
}
