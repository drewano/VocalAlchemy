import { Outlet } from "react-router-dom"
import { AppSidebar } from "@/components/app-sidebar"
import { SidebarInset, SidebarProvider, SidebarRail } from "@/components/ui/sidebar"

export default function DashboardLayout() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarRail />
      <SidebarInset>
        <div className="flex-1 p-6 md:p-8 mx-auto max-w-6xl w-full">
          <Outlet />
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
