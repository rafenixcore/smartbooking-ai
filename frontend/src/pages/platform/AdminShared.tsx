import { ReactNode } from 'react'
import { AlertCircle, Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'

export function PageHeading({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return (
    <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div><h1 className="text-2xl font-bold tracking-tight md:text-3xl">{title}</h1><p className="mt-2 max-w-2xl text-sm text-muted-foreground">{description}</p></div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

export function LoadingState({ label = 'Cargando información…' }: { label?: string }) {
  return <div role="status" className="flex min-h-44 items-center justify-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />{label}</div>
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div role="alert" className="flex items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /><div className="flex-1"><p>{message}</p>{onRetry && <button type="button" className="mt-2 font-semibold underline" onClick={onRetry}>Intentar de nuevo</button>}</div></div>
}

export function StatusBadge({ active, label }: { active: boolean; label?: string }) {
  return <Badge variant={active ? 'success' : 'destructive'}>{label ?? (active ? 'Activo' : 'Suspendido')}</Badge>
}

export function InvitationBadge({ status, delivery }: { status: string; delivery?: string }) {
  const statusText: Record<string, string> = { pending: 'Pendiente', accepted: 'Aceptada', expired: 'Vencida', revoked: 'Revocada' }
  const variant = status === 'accepted' ? 'success' : status === 'pending' ? 'warning' : 'secondary'
  return <div className="flex flex-wrap items-center gap-2"><Badge variant={variant}>{statusText[status] ?? status}</Badge>{delivery === 'failed' && <Badge variant="destructive">Correo fallido</Badge>}</div>
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return <div className="rounded-xl border border-dashed border-border px-6 py-12 text-center"><p className="font-semibold">{title}</p><p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">{description}</p></div>
}
