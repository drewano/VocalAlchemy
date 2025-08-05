import * as React from "react"
import { Link } from "react-router-dom"
import { Pencil } from "lucide-react"
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
  SidebarSeparator,
} from "@/components/ui/sidebar"

function truncate(text: string, max = 40) {
  if (!text) return ""
  return text.length > max ? text.slice(0, max) + "…" : text
}

export function AppSidebar({ onSearchChange, ...props }: React.ComponentProps<typeof Sidebar> & { onSearchChange?: (term: string) => void }) {
  const { history, isLoading } = useAnalysisHistory()

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
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild>
              <Link to="/prompts">
                <Pencil />
                <span>Gérer les prompts</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
        <SidebarSeparator />
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
      <SidebarFooter>{/* User/account controls could go here later */}</SidebarFooter>
    </Sidebar>
  )
}
