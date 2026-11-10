import { useEffect } from 'react'
import { Navigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { usePlatformAuthStore } from '@/store/platformAuthStore'
import AdminLayout from './AdminLayout'

export default function AdminRoutes() {
  const { admin, ready, initialize } = usePlatformAuthStore()

  useEffect(() => {
    if (!ready) void initialize()
  }, [ready, initialize])

  if (!ready) {
    return (
      <main className="flex min-h-screen items-center justify-center gap-3 bg-muted/30 text-sm text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
        Validando acceso administrativo…
      </main>
    )
  }
  if (!admin) return <Navigate to="/admin/login" replace />
  return <AdminLayout />
}
