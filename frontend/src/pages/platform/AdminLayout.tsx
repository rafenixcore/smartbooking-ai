import { ReactNode } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { BarChart3, Building2, LayoutDashboard, LogOut, Mail, ScrollText, ShieldCheck } from 'lucide-react'
import { usePlatformAuthStore } from '@/store/platformAuthStore'
import { cn } from '@/utils/cn'
import BrandMark from '@/components/BrandMark'

const navigation = [
  { to: '/admin', label: 'Resumen', icon: LayoutDashboard, end: true },
  { to: '/admin/businesses', label: 'Negocios', icon: Building2 },
  { to: '/admin/invitations', label: 'Invitaciones', icon: Mail },
  { to: '/admin/metrics', label: 'Métricas', icon: BarChart3 },
  { to: '/admin/audit', label: 'Actividad', icon: ScrollText },
]

function NavigationLink({ item, mobile = false }: { item: typeof navigation[number]; mobile?: boolean }) {
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      end={item.end}
      className={({ isActive }) => cn(
        'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors',
        isActive ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
        mobile && 'shrink-0 px-3 py-2'
      )}
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
      {item.label}
    </NavLink>
  )
}

export default function AdminLayout({ children }: { children?: ReactNode }) {
  const navigate = useNavigate()
  const { admin, logout } = usePlatformAuthStore()

  const leave = async () => {
    await logout().catch(() => undefined)
    navigate('/admin/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-muted/30 lg:flex">
      <aside className="hidden w-64 shrink-0 border-r border-border/70 bg-card lg:flex lg:flex-col">
        <div className="flex h-20 items-center gap-3 border-b border-border/70 px-6">
          <BrandMark size={40} className="rounded-xl" />
          <div><p className="font-semibold leading-tight">SmartBooking</p><p className="mt-1 text-xs text-muted-foreground">Rafenixcore · Plataforma</p></div>
        </div>
        <nav aria-label="Administración" className="flex-1 space-y-1 p-4">
          {navigation.map((item) => <NavigationLink key={item.to} item={item} />)}
        </nav>
        <div className="border-t border-border/70 p-4">
          <div className="mb-3 flex items-center gap-2 px-2 text-xs text-muted-foreground">
            <ShieldCheck className="h-4 w-4 text-primary" aria-hidden="true" /> Administrador de plataforma
          </div>
          <button type="button" onClick={() => void leave()} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
            <LogOut className="h-4 w-4" aria-hidden="true" /> Cerrar sesión
          </button>
        </div>
      </aside>

      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <header className="border-b border-border/70 bg-card/90 px-4 py-3 backdrop-blur md:px-8 lg:flex lg:h-20 lg:items-center lg:justify-between lg:px-10">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 lg:hidden">
              <BrandMark size={36} className="rounded-lg" />
              <div><p className="text-sm font-semibold">SmartBooking</p><p className="text-[11px] text-muted-foreground">Administración</p></div>
            </div>
            <div className="hidden lg:block">
              <p className="text-sm font-semibold">Panel de plataforma</p>
              <p className="mt-0.5 text-xs text-muted-foreground">Gestión segura de negocios e invitaciones</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="hidden text-right sm:block"><p className="text-sm font-medium">{admin?.email}</p><p className="text-xs text-muted-foreground">Administrador</p></div>
              <button type="button" onClick={() => void leave()} aria-label="Cerrar sesión" className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground lg:hidden">
                <LogOut className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </div>
          <nav aria-label="Navegación móvil" className="mt-3 flex gap-1 overflow-x-auto lg:hidden">
            {navigation.map((item) => <NavigationLink key={item.to} item={item} mobile />)}
          </nav>
        </header>

        <main className="w-full flex-1 px-4 py-6 md:px-8 md:py-8 lg:px-10">
          <div className="mx-auto max-w-7xl">{children ?? <Outlet />}</div>
        </main>
      </div>
    </div>
  )
}
