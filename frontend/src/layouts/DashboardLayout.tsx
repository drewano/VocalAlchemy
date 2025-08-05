import { Outlet } from "react-router-dom"
import { useState } from "react"
import { AppSidebar } from "@/components/app-sidebar"
import { SiteHeader } from "@/components/site-header"
import { SidebarInset, SidebarProvider, SidebarRail } from "@/components/ui/sidebar"

export default function DashboardLayout() {
  const [searchTerm, setSearchTerm] = useState("")

  return (
    <SidebarProvider>
      <AppSidebar onSearchChange={setSearchTerm} />
      <SidebarRail />
      <SidebarInset>
        <SiteHeader />
        <div className="flex-1 p-4 sm:p-6">
          <Outlet context={{ searchTerm }} />
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
