import { FormEvent, useCallback, useEffect, useState } from 'react'
import { CalendarDays, ChevronLeft, ChevronRight, CircleDollarSign, MessageCircle, RefreshCw, Users } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { platformAPI } from '@/services/api'
import type { PlatformMetricCost, PlatformMetricSummary, PlatformMetricsResponse } from '@/types/platform'
import { EmptyState, ErrorState, LoadingState, PageHeading } from './AdminShared'

const PAGE_SIZE = 25
const STATUS_LABELS: Record<string, string> = {
  P: 'Pendiente', C: 'Confirmada', A: 'Cancelada', D: 'Completada',
  sent: 'Enviado', delivered: 'Entregado', read: 'Leído', failed: 'Fallido',
}
const STATUS_COLORS: Record<string, string> = {
  P: 'bg-amber-500', C: 'bg-blue-500', A: 'bg-slate-400', D: 'bg-emerald-500',
  sent: 'bg-sky-500', delivered: 'bg-emerald-500', read: 'bg-teal-500', failed: 'bg-rose-500',
}

function dateInputValue(date: Date) {
  return date.toISOString().slice(0, 10)
}

function initialRange() {
  const today = new Date()
  const end = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()))
  const start = new Date(end)
  start.setUTCDate(start.getUTCDate() - 29)
  return { from: dateInputValue(start), through: dateInputValue(end) }
}

function isoStart(date: string) {
  return `${date}T00:00:00Z`
}

function isoEndExclusive(date: string) {
  const end = new Date(`${date}T00:00:00Z`)
  end.setUTCDate(end.getUTCDate() + 1)
  return end.toISOString()
}

function formatCount(value: number) {
  return new Intl.NumberFormat('es-DO').format(value)
}

function formatMoney(cost: PlatformMetricCost) {
  if (cost.amount === null || !cost.currency) return null
  const amount = Number(cost.amount)
  if (!Number.isFinite(amount)) return null
  try {
    return new Intl.NumberFormat('es-DO', {
      style: 'currency', currency: cost.currency, maximumFractionDigits: 6,
    }).format(amount)
  } catch {
    return `${cost.amount} ${cost.currency}`
  }
}

function costLabel(status: PlatformMetricCost['status']) {
  if (status === 'actual') return 'Conciliado'
  if (status === 'estimated') return 'Estimado'
  return 'No disponible'
}

function CostBadge({ cost }: { cost: PlatformMetricCost }) {
  const variant = cost.status === 'actual' ? 'success' : cost.status === 'estimated' ? 'warning' : 'secondary'
  return <Badge variant={variant}>{costLabel(cost.status)}</Badge>
}

function StatusBreakdown({ title, rows }: { title: string; rows: Record<string, number> }) {
  const values = Object.entries(rows)
  const total = values.reduce((sum, [, count]) => sum + count, 0)
  return (
    <div>
      <p className="mb-3 text-sm font-semibold">{title}</p>
      {values.length === 0 || total === 0 ? <p className="text-sm text-muted-foreground">Sin eventos en este periodo.</p> : <>
        <div className="flex h-2 overflow-hidden rounded-full bg-muted" aria-label={`${title}: ${formatCount(total)} en total`}>
          {values.filter(([, count]) => count > 0).map(([status, count]) => (
            <span key={status} className={`${STATUS_COLORS[status] ?? 'bg-primary'} first:rounded-l-full last:rounded-r-full`} style={{ width: `${total ? (count / total) * 100 : 0}%` }} />
          ))}
        </div>
        <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-4">
          {values.map(([status, count]) => <li key={status} className="flex items-center justify-between gap-2 text-muted-foreground">
            <span className="flex min-w-0 items-center gap-2"><span className={`h-2 w-2 shrink-0 rounded-full ${STATUS_COLORS[status] ?? 'bg-primary'}`} />{STATUS_LABELS[status] ?? status}</span>
            <span className="font-semibold tabular-nums text-foreground">{formatCount(count)}</span>
          </li>)}
        </ul>
      </>}
    </div>
  )
}

function CostDetails({ cost }: { cost: PlatformMetricCost }) {
  const money = formatMoney(cost)
  return <div className="min-w-40">
    <div className="flex flex-wrap items-center gap-2"><CostBadge cost={cost} />
      {money && <span className="font-semibold tabular-nums">{money}</span>}
    </div>
    {cost.status === 'unavailable' && <p className="mt-1 text-xs text-muted-foreground">Entregados con tarifa: {cost.coverage.priced}/{cost.coverage.delivered}</p>}
    {cost.status !== 'unavailable' && <>
      {cost.source_reference && <p className="mt-1 max-w-64 break-all text-xs text-muted-foreground" title={cost.source_reference}>Fuente: {cost.source_reference}</p>}
      {cost.rate_versions.length > 0 && <p className="mt-1 text-xs text-muted-foreground">Tarifa: {cost.rate_versions.join(', ')}</p>}
    </>}
  </div>
}

function SummaryCard({ title, value, detail, icon: Icon, accent }: {
  title: string; value: string; detail: string; icon: typeof CalendarDays; accent: string
}) {
  return <Card className="border-border/70 shadow-sm">
    <CardContent className="flex items-start justify-between gap-3 p-5">
      <div className="min-w-0"><p className="text-sm text-muted-foreground">{title}</p><p className="mt-2 text-2xl font-bold tracking-tight tabular-nums">{value}</p><p className="mt-1 text-xs text-muted-foreground">{detail}</p></div>
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${accent}`}><Icon className="h-5 w-5" aria-hidden="true" /></div>
    </CardContent>
  </Card>
}

function globalCostLabel(cost: PlatformMetricCost) {
  if (cost.status !== 'unavailable') return `${cost.status === 'actual' ? 'Conciliado' : 'Estimado'} · ${formatMoney(cost) ?? 'Importe disponible'}`
  const reasons: Record<string, string> = {
    no_businesses: 'Todavía no hay negocios registrados.',
    no_delivered_messages: 'No hay mensajes entregados en el periodo.',
    incomplete_coverage: 'Falta una tarifa verificada o cobertura completa.',
    partial_reconciliation: 'La conciliación no cubre todos los negocios.',
  }
  return reasons[cost.reason ?? ''] ?? 'No hay datos suficientes para calcular un importe.'
}

function getTotal(summary: PlatformMetricSummary, statuses: string[]) {
  return statuses.reduce((sum, status) => sum + (summary.messages.by_status[status] ?? 0), 0)
}

export default function Metrics() {
  const [range, setRange] = useState(initialRange)
  const [appliedRange, setAppliedRange] = useState(initialRange)
  const [offset, setOffset] = useState(0)
  const [data, setData] = useState<PlatformMetricsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [rangeError, setRangeError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const result = await platformAPI.getMetrics({
        from: isoStart(appliedRange.from),
        to: isoEndExclusive(appliedRange.through),
        offset,
        limit: PAGE_SIZE,
      })
      setData(result)
    } catch {
      setError('No fue posible cargar las métricas. Inténtalo de nuevo.')
    } finally {
      setLoading(false)
    }
  }, [appliedRange, offset])

  useEffect(() => { void load() }, [load])

  const submitRange = (event: FormEvent) => {
    event.preventDefault()
    if (!range.from || !range.through || range.from > range.through) {
      setRangeError('Selecciona un periodo válido: la fecha inicial debe ser anterior o igual a la final.')
      return
    }
    const days = (Date.parse(`${range.through}T00:00:00Z`) - Date.parse(`${range.from}T00:00:00Z`)) / 86_400_000 + 1
    if (days > 366) {
      setRangeError('El periodo no puede superar 366 días.')
      return
    }
    setRangeError('')
    setOffset(0)
    setAppliedRange(range)
  }

  const global = data?.global
  const delivered = global ? getTotal(global, ['delivered', 'read']) : 0
  const cost = global?.cost
  const businesses = data?.businesses
  const startLabel = data ? new Date(data.period.start).toLocaleDateString('es-DO', { timeZone: 'UTC' }) : ''
  const endLabel = data ? new Date(Date.parse(data.period.end) - 1).toLocaleDateString('es-DO', { timeZone: 'UTC' }) : ''

  return <>
    <PageHeading title="Métricas" description="Actividad de citas y WhatsApp por periodo, con definiciones y fuente visibles." action={
      <Button variant="outline" onClick={() => void load()} isLoading={loading}><RefreshCw className="h-4 w-4" aria-hidden="true" /> Actualizar</Button>
    } />

    <Card className="mb-6 border-border/70 shadow-sm">
      <CardContent className="flex flex-col gap-4 p-4 md:flex-row md:items-end md:justify-between md:p-5">
        <form onSubmit={submitRange} className="grid flex-1 gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <Input type="date" label="Desde (UTC)" value={range.from} max={range.through} onChange={(event) => setRange((current) => ({ ...current, from: event.target.value }))} />
          <Input type="date" label="Hasta (UTC)" value={range.through} min={range.from} onChange={(event) => setRange((current) => ({ ...current, through: event.target.value }))} />
          <Button type="submit" className="w-full sm:w-auto">Aplicar periodo</Button>
        </form>
        <p className="max-w-xs text-xs leading-5 text-muted-foreground">El intervalo incluye ambos días seleccionados. Los datos se consultan en UTC.</p>
      </CardContent>
      {rangeError && <p role="alert" className="px-5 pb-4 text-sm text-destructive">{rangeError}</p>}
    </Card>

    {loading ? <LoadingState label="Cargando métricas…" /> : error ? <ErrorState message={error} onRetry={() => void load()} /> : data && global ? <>
      <div className="mb-5 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <CalendarDays className="h-4 w-4" aria-hidden="true" />
        <span>Periodo: <strong className="font-semibold text-foreground">{startLabel} – {endLabel} UTC</strong></span>
        <Badge variant="outline">{data.businesses.total} negocios</Badge>
      </div>

      <section aria-label="Resumen global" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard title="Citas registradas" value={formatCount(global.appointments.total)} detail="Todos los estados incluidos" icon={CalendarDays} accent="bg-blue-500/10 text-blue-700 dark:text-blue-400" />
        <SummaryCard title="Clientes con citas" value={formatCount(global.customers_with_appointments)} detail="Personas distintas en el periodo" icon={Users} accent="bg-violet-500/10 text-violet-700 dark:text-violet-400" />
        <SummaryCard title="Mensajes salientes" value={formatCount(global.messages.total)} detail={`${formatCount(delivered)} entregados o leídos`} icon={MessageCircle} accent="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" />
        <Card className="border-border/70 shadow-sm">
          <CardContent className="flex items-start justify-between gap-3 p-5">
            <div><p className="text-sm text-muted-foreground">Costo de WhatsApp</p>
              <div className="mt-2"><CostBadge cost={global.cost} /></div>
              <p className="mt-2 text-sm font-semibold leading-5">{globalCostLabel(global.cost)}</p>
              <p className="mt-1 text-xs text-muted-foreground">Cobertura entregados: {formatCount(global.cost.coverage.priced)}/{formatCount(global.cost.coverage.delivered)}</p>
              {global.cost.status !== 'unavailable' && global.cost.source_reference && <p className="mt-1 break-all text-xs text-muted-foreground" title={global.cost.source_reference}>Fuente: {global.cost.source_reference}</p>}
              {global.cost.rate_versions.length > 0 && <p className="mt-1 text-xs text-muted-foreground">Tarifa: {global.cost.rate_versions.join(', ')}</p>}
            </div>
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-500/10 text-amber-700 dark:text-amber-400"><CircleDollarSign className="h-5 w-5" aria-hidden="true" /></div>
          </CardContent>
        </Card>
      </section>

      <section className="mt-5 grid gap-4 lg:grid-cols-2">
        <Card className="border-border/70 shadow-sm"><CardContent className="p-5 md:p-6"><StatusBreakdown title="Citas por estado" rows={global.appointments.by_status} /></CardContent></Card>
        <Card className="border-border/70 shadow-sm"><CardContent className="p-5 md:p-6"><StatusBreakdown title="Mensajes de WhatsApp por último estado" rows={global.messages.by_status} /><p className="mt-3 text-xs leading-5 text-muted-foreground">Cada mensaje cuenta una vez por su último estado conocido en este periodo. No se suman los cambios de estado repetidos.</p></CardContent></Card>
      </section>

      <section className="mt-8">
        <div className="mb-4 flex items-end justify-between gap-3"><div><h2 className="text-lg font-semibold">Detalle por negocio</h2><p className="mt-1 text-sm text-muted-foreground">Conteos y cobertura de costo para el mismo periodo.</p></div><span className="text-xs text-muted-foreground">Fuente: citas y registro de mensajes</span></div>
        {businesses && businesses.items.length === 0 ? <EmptyState title="No hay negocios para mostrar" description="Cuando se incorporen negocios, sus conteos y cobertura aparecerán aquí. El resumen global seguirá mostrando los datos disponibles." /> : businesses && <>
          <Card className="hidden overflow-hidden border-border/70 shadow-sm md:block">
            <Table><TableHeader><TableRow><TableHead>Negocio</TableHead><TableHead className="text-right">Citas</TableHead><TableHead className="text-right">Clientes</TableHead><TableHead className="text-right">Mensajes</TableHead><TableHead>Costo y cobertura</TableHead></TableRow></TableHeader>
              <TableBody>{businesses.items.map((business) => <TableRow key={business.business_id}>
                <TableCell className="min-w-48"><p className="font-medium">{business.business_name}</p><p className="mt-1 text-xs text-muted-foreground">ID #{business.business_id}</p></TableCell>
                <TableCell className="text-right tabular-nums">{formatCount(business.appointments.total)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatCount(business.customers_with_appointments)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatCount(business.messages.total)}</TableCell>
                <TableCell><CostDetails cost={business.cost} /></TableCell>
              </TableRow>)}</TableBody>
            </Table>
          </Card>
          <div className="grid gap-3 md:hidden">{businesses.items.map((business) => <Card key={business.business_id} className="border-border/70 shadow-sm"><CardContent className="p-4">
            <div className="flex items-start justify-between gap-3"><div><p className="font-semibold">{business.business_name}</p><p className="mt-1 text-xs text-muted-foreground">Negocio #{business.business_id}</p></div><CostBadge cost={business.cost} /></div>
            <dl className="mt-4 grid grid-cols-3 gap-2 text-sm"><div><dt className="text-xs text-muted-foreground">Citas</dt><dd className="mt-1 font-semibold tabular-nums">{formatCount(business.appointments.total)}</dd></div><div><dt className="text-xs text-muted-foreground">Clientes</dt><dd className="mt-1 font-semibold tabular-nums">{formatCount(business.customers_with_appointments)}</dd></div><div><dt className="text-xs text-muted-foreground">Mensajes</dt><dd className="mt-1 font-semibold tabular-nums">{formatCount(business.messages.total)}</dd></div></dl>
            <div className="mt-4 border-t border-border/70 pt-3"><CostDetails cost={business.cost} /></div>
          </CardContent></Card>)}</div>
          <div className="mt-4 flex flex-col gap-3 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
            <p>Mostrando {businesses.total === 0 ? 0 : offset + 1}–{Math.min(offset + businesses.items.length, businesses.total)} de {formatCount(businesses.total)}</p>
            <div className="flex gap-2"><Button variant="outline" size="sm" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}><ChevronLeft className="h-4 w-4" aria-hidden="true" /> Anterior</Button><Button variant="outline" size="sm" disabled={offset + PAGE_SIZE >= businesses.total || loading} onClick={() => setOffset(offset + PAGE_SIZE)}>Siguiente <ChevronRight className="h-4 w-4" aria-hidden="true" /></Button></div>
          </div>
        </>}
      </section>

      <details className="mt-7 rounded-xl border border-border/70 bg-card px-4 py-3 text-sm">
        <summary className="cursor-pointer font-medium">Definiciones y fuentes</summary>
        <dl className="mt-4 grid gap-4 md:grid-cols-2">{Object.entries(data.definitions).map(([key, definition]) => <div key={key}>
          <dt className="font-semibold">{key === 'customers_with_appointments' ? 'Clientes con citas' : key === 'cost' ? 'Costo' : key === 'messages' ? 'Mensajes' : 'Citas'} <span className="font-normal text-muted-foreground">· {definition.source}</span></dt><dd className="mt-1 text-xs leading-5 text-muted-foreground">{definition.formula}</dd>
        </div>)}</dl>
        {cost?.status === 'unavailable' && <p className="mt-4 border-t border-border/70 pt-3 text-xs leading-5 text-muted-foreground">El costo solo se muestra con una tarifa documentada o una conciliación de facturación completa. Este panel no incorpora tarifas supuestas.</p>}
      </details>
    </> : null}
  </>
}
