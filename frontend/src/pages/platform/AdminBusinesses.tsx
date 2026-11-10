import { FormEvent, useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Search, UserPlus } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { platformAPI } from '@/services/api'
import type { PlatformBusiness, PlatformBusinessPage } from '@/types/platform'
import { EmptyState, ErrorState, LoadingState, PageHeading, StatusBadge } from './AdminShared'
import { formatDate } from './platformUtils'

const PAGE_SIZE = 10

export default function AdminBusinesses() {
  const [page, setPage] = useState<PlatformBusinessPage | null>(null)
  const [offset, setOffset] = useState(0)
  const [status, setStatus] = useState<'all' | 'active' | 'suspended'>('all')
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setPage(await platformAPI.listBusinesses({
        offset,
        limit: PAGE_SIZE,
        status: status === 'all' ? undefined : status,
        q: search || undefined,
      }))
    } catch {
      setError('No fue posible cargar los negocios.')
    } finally {
      setLoading(false)
    }
  }, [offset, search, status])

  useEffect(() => { void load() }, [load])

  const submitSearch = (event: FormEvent) => {
    event.preventDefault()
    setOffset(0)
    setSearch(query.trim())
  }

  return (
    <>
      <PageHeading title="Negocios" description="Consulta el estado de las cuentas y administra su acceso operativo." action={
        <Link to="/admin/invitations" className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-5 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"><UserPlus className="h-4 w-4" aria-hidden="true" /> Invitar dueño</Link>
      } />

      <Card className="mb-5 border-border/70 p-4 shadow-sm md:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <form onSubmit={submitSearch} className="flex w-full flex-col gap-3 sm:flex-row lg:max-w-xl">
            <div className="flex-1"><Input label="Buscar" placeholder="Nombre del negocio o correo del dueño" value={query} onChange={(event) => setQuery(event.target.value)} /></div>
            <Button type="submit" variant="outline" className="sm:mb-0.5"><Search className="h-4 w-4" aria-hidden="true" /> Buscar</Button>
          </form>
          <Select label="Estado" value={status} onChange={(event) => { setStatus(event.target.value as typeof status); setOffset(0) }} className="min-w-44" options={[
            { value: 'all', label: 'Todos' }, { value: 'active', label: 'Activos' }, { value: 'suspended', label: 'Suspendidos' },
          ]} />
        </div>
      </Card>

      {loading ? <LoadingState label="Cargando negocios…" /> : error ? <ErrorState message={error} onRetry={() => void load()} /> : !page || page.items.length === 0 ? (
        <EmptyState title="No encontramos negocios" description={search ? 'Prueba con otro nombre o correo, o limpia la búsqueda.' : 'Los negocios invitados aparecerán aquí cuando completen su alta.'} />
      ) : <>
        <Card className="overflow-hidden border-border/70 shadow-sm">
          <Table>
            <TableHeader><TableRow><TableHead>Negocio</TableHead><TableHead>Dueño</TableHead><TableHead>Estado</TableHead><TableHead>Alta</TableHead><TableHead>Creado</TableHead><TableHead><span className="sr-only">Abrir detalle</span></TableHead></TableRow></TableHeader>
            <TableBody>{page.items.map((business: PlatformBusiness) => <TableRow key={business.id}>
              <TableCell><p className="font-semibold">{business.name}</p><p className="mt-1 text-xs text-muted-foreground">ID #{business.id}</p></TableCell>
              <TableCell className="max-w-56 truncate text-sm">{business.owner_email ?? 'Sin dueño asociado'}</TableCell>
              <TableCell><StatusBadge active={business.is_active} label={business.is_active ? 'Acceso habilitado' : 'Suspendido'} /></TableCell>
              <TableCell><span className={business.onboarding_complete ? 'text-sm text-foreground' : 'text-sm text-amber-700 dark:text-amber-400'}>{business.onboarding_complete ? 'Completa' : 'Pendiente'}</span></TableCell>
              <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{formatDate(business.created_at)}</TableCell>
              <TableCell><Link to={`/admin/businesses/${business.id}`} aria-label={`Ver ${business.name}`} className="inline-flex rounded-lg p-2 text-primary hover:bg-primary/10"><ArrowRight className="h-4 w-4" aria-hidden="true" /></Link></TableCell>
            </TableRow>)}</TableBody>
          </Table>
        </Card>
        <div className="mt-4 flex flex-col gap-3 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>Mostrando {offset + 1}–{Math.min(offset + page.items.length, page.total)} de {page.total}</p>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Anterior</Button>
            <Button variant="outline" size="sm" disabled={offset + PAGE_SIZE >= page.total} onClick={() => setOffset(offset + PAGE_SIZE)}>Siguiente</Button>
          </div>
        </div>
      </>}
    </>
  )
}
