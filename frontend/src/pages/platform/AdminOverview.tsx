import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, ArrowRight, Building2, Mail, PauseCircle } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/Card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { platformAPI } from '@/services/api'
import type { AdminAuditEvent } from '@/types/platform'
import { ErrorState, LoadingState, PageHeading } from './AdminShared'
import { formatDate } from './platformUtils'

interface OverviewData {
  active: number
  suspended: number
  invitations: number
  recent: AdminAuditEvent[]
}

const metrics = [
  { key: 'active' as const, label: 'Negocios con acceso habilitado', icon: Building2, tint: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400' },
  { key: 'suspended' as const, label: 'Negocios suspendidos', icon: PauseCircle, tint: 'bg-amber-500/10 text-amber-700 dark:text-amber-400' },
  { key: 'invitations' as const, label: 'Invitaciones pendientes', icon: Mail, tint: 'bg-blue-500/10 text-blue-700 dark:text-blue-400' },
]

function actionLabel(action: string): string {
  const labels: Record<string, string> = {
    'business.suspend': 'Suspendió un negocio',
    'business.reactivate': 'Reactivó un negocio',
    'owner_invitation.create': 'Envió una invitación',
    'owner_invitation.resend': 'Reenvió una invitación',
    'owner_invitation.revoke': 'Revocó una invitación',
  }
  return labels[action] ?? action.replace(/\./g, ' ')
}

export default function AdminOverview() {
  const [data, setData] = useState<OverviewData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [active, suspended, invitations, audit] = await Promise.all([
        platformAPI.listBusinesses({ status: 'active', limit: 1 }),
        platformAPI.listBusinesses({ status: 'suspended', limit: 1 }),
        platformAPI.listInvitations({ status: 'pending', limit: 1 }),
        platformAPI.listAudit({ limit: 6 }),
      ])
      setData({ active: active.total, suspended: suspended.total, invitations: invitations.total, recent: audit.items })
    } catch {
      setError('No fue posible cargar el resumen administrativo.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  return (
    <>
      <PageHeading title="Resumen" description="Estado de incorporación y últimas acciones de SmartBooking." />
      {loading ? <LoadingState label="Cargando resumen…" /> : error ? <ErrorState message={error} onRetry={() => void load()} /> : data && <>
        <section aria-label="Estado de la plataforma" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {metrics.map(({ key, label, icon: Icon, tint }) => (
            <Card key={key} className="border-border/70 shadow-sm">
              <CardContent className="flex items-center justify-between gap-4 p-5 md:p-6">
                <div><p className="text-sm text-muted-foreground">{label}</p><p className="mt-2 text-3xl font-bold tabular-nums">{data[key]}</p></div>
                <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${tint}`}><Icon className="h-5 w-5" aria-hidden="true" /></div>
              </CardContent>
            </Card>
          ))}
        </section>

        <section className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(260px,0.8fr)]">
          <Card className="border-border/70 shadow-sm">
            <div className="flex items-center justify-between border-b border-border/70 px-5 py-4 md:px-6">
              <div><h2 className="font-semibold">Actividad reciente</h2><p className="mt-1 text-xs text-muted-foreground">Acciones administrativas registradas</p></div>
              <Link to="/admin/audit" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">Ver bitácora <ArrowRight className="h-4 w-4" aria-hidden="true" /></Link>
            </div>
            {data.recent.length === 0 ? <div className="p-5"><p className="text-sm text-muted-foreground">Todavía no hay acciones administrativas registradas.</p></div> : (
              <Table>
                <TableHeader><TableRow><TableHead>Acción</TableHead><TableHead>Resultado</TableHead><TableHead className="text-right">Fecha</TableHead></TableRow></TableHeader>
                <TableBody>{data.recent.map((event) => <TableRow key={event.id}>
                  <TableCell><p className="font-medium">{actionLabel(event.action)}</p><p className="mt-1 text-xs text-muted-foreground">{event.entity_type === 'business' ? 'Negocio' : 'Invitación'} · #{event.entity_id}</p></TableCell>
                  <TableCell className="capitalize text-muted-foreground">{event.outcome === 'success' ? 'Correcto' : event.outcome === 'unchanged' ? 'Sin cambios' : event.outcome}</TableCell>
                  <TableCell className="text-right text-xs text-muted-foreground">{formatDate(event.created_at)}</TableCell>
                </TableRow>)}</TableBody>
              </Table>
            )}
          </Card>

          <Card className="border-border/70 shadow-sm">
            <CardContent className="p-5 md:p-6">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><Activity className="h-5 w-5" aria-hidden="true" /></div>
              <h2 className="mt-4 font-semibold">Mensajes y costos</h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">La actividad de WhatsApp y su cobertura están disponibles en métricas. Este resumen no presenta estimaciones como gasto real.</p>
              <Link to="/admin/metrics" className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">Ver métricas <ArrowRight className="h-4 w-4" aria-hidden="true" /></Link>
            </CardContent>
          </Card>
        </section>
      </>}
    </>
  )
}
