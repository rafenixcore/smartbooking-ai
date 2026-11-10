import { useCallback, useEffect, useState } from 'react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { platformAPI } from '@/services/api'
import type { AdminAuditPage } from '@/types/platform'
import { EmptyState, ErrorState, LoadingState, PageHeading } from './AdminShared'
import { formatDate } from './platformUtils'

const PAGE_SIZE = 20

function describeAction(action: string): string {
  const labels: Record<string, string> = {
    'business.suspend': 'Suspensión de negocio',
    'business.reactivate': 'Reactivación de negocio',
    'owner_invitation.create': 'Invitación creada',
    'owner_invitation.resend': 'Invitación reenviada',
    'owner_invitation.revoke': 'Invitación revocada',
  }
  return labels[action] ?? action.replace(/\./g, ' ')
}

function resultLabel(outcome: string): string {
  const labels: Record<string, string> = { success: 'Correcto', unchanged: 'Sin cambios', not_found: 'No encontrado' }
  return labels[outcome] ?? outcome
}

export default function AdminAudit() {
  const [page, setPage] = useState<AdminAuditPage | null>(null)
  const [offset, setOffset] = useState(0)
  const [entity, setEntity] = useState<'all' | 'business' | 'owner_invitation'>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setPage(await platformAPI.listAudit({ offset, limit: PAGE_SIZE, entity_type: entity === 'all' ? undefined : entity }))
    } catch {
      setError('No fue posible cargar la bitácora administrativa.')
    } finally {
      setLoading(false)
    }
  }, [entity, offset])

  useEffect(() => { void load() }, [load])

  return <>
    <PageHeading title="Actividad administrativa" description="Registro de acciones sobre negocios e invitaciones. Se muestran el actor, el recurso y el resultado; no se exponen tokens ni contenido de mensajes." />
    <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm text-muted-foreground">{page ? `${page.total} eventos registrados` : 'Eventos administrativos'}</p>
      <label className="text-sm text-muted-foreground">Tipo de actividad
        <select value={entity} onChange={(event) => { setEntity(event.target.value as typeof entity); setOffset(0) }} className="ml-2 h-10 rounded-lg border border-input bg-background px-3 text-sm text-foreground">
          <option value="all">Todas</option><option value="business">Negocios</option><option value="owner_invitation">Invitaciones</option>
        </select>
      </label>
    </div>
    {loading ? <LoadingState label="Cargando actividad…" /> : error ? <ErrorState message={error} onRetry={() => void load()} /> : !page || page.items.length === 0 ? <EmptyState title="Todavía no hay actividad" description="Las acciones administrativas aparecerán aquí cuando se gestionen negocios o invitaciones." /> : <>
      <Card className="overflow-hidden border-border/70 shadow-sm">
        <Table>
          <TableHeader><TableRow><TableHead>Acción</TableHead><TableHead>Administrador</TableHead><TableHead>Resultado</TableHead><TableHead>Fecha</TableHead></TableRow></TableHeader>
          <TableBody>{page.items.map((event) => <TableRow key={event.id}>
            <TableCell><p className="font-medium">{describeAction(event.action)}</p><p className="mt-1 text-xs text-muted-foreground">{event.entity_type === 'business' ? 'Negocio' : 'Invitación'} · #{event.entity_id}</p></TableCell>
            <TableCell className="text-sm">ID #{event.admin_id}</TableCell>
            <TableCell className="text-sm text-muted-foreground">{resultLabel(event.outcome)}</TableCell>
            <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{formatDate(event.created_at)}</TableCell>
          </TableRow>)}</TableBody>
        </Table>
      </Card>
      <div className="mt-4 flex flex-col gap-3 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <p>Mostrando {offset + 1}–{Math.min(offset + page.items.length, page.total)} de {page.total}</p>
        <div className="flex gap-2"><Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Anterior</Button><Button variant="outline" size="sm" disabled={offset + PAGE_SIZE >= page.total} onClick={() => setOffset(offset + PAGE_SIZE)}>Siguiente</Button></div>
      </div>
    </>}
  </>
}
