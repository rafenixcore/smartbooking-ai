import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Building2, CheckCircle2, PauseCircle, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { platformAPI } from '@/services/api'
import type { PlatformBusiness } from '@/types/platform'
import { ErrorState, LoadingState, PageHeading, StatusBadge } from './AdminShared'
import { formatDate } from './platformUtils'

export default function AdminBusinessDetail() {
  const { businessId } = useParams()
  const parsedId = Number(businessId)
  const [business, setBusiness] = useState<PlatformBusiness | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [confirmSuspend, setConfirmSuspend] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      if (!Number.isSafeInteger(parsedId) || parsedId < 1) throw new Error('invalid id')
      setBusiness(await platformAPI.getBusiness(parsedId))
    } catch {
      setError('No se pudo encontrar este negocio o no tienes acceso a sus datos.')
    } finally {
      setLoading(false)
    }
  }, [parsedId])

  useEffect(() => { void load() }, [load])

  const setActive = async (active: boolean) => {
    if (!business) return
    setSaving(true)
    setError('')
    try {
      setBusiness(await platformAPI.setBusinessActive(business.id, active))
      setConfirmSuspend(false)
    } catch {
      setError('No se pudo actualizar el acceso. Vuelve a intentarlo.')
    } finally {
      setSaving(false)
    }
  }

  return <>
    <Link to="/admin/businesses" className="mb-5 inline-flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" aria-hidden="true" /> Volver a negocios</Link>
    {loading ? <LoadingState label="Cargando negocio…" /> : error && !business ? <ErrorState message={error} onRetry={() => void load()} /> : business && <>
      <PageHeading
        title={business.name}
        description={`Cuenta de negocio · ID #${business.id}`}
        action={business.is_active
          ? <Button variant="danger" onClick={() => setConfirmSuspend(true)}><PauseCircle className="h-4 w-4" aria-hidden="true" /> Suspender negocio</Button>
          : <Button onClick={() => void setActive(true)} isLoading={saving}><RotateCcw className="h-4 w-4" aria-hidden="true" /> Reactivar negocio</Button>}
      />

      {error && <div className="mb-5"><ErrorState message={error} /></div>}

      {confirmSuspend && <Card className="mb-5 border-amber-500/30 bg-amber-500/5"><CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div><p className="font-semibold">¿Suspender este negocio?</p><p className="mt-1 text-sm text-muted-foreground">El dueño dejará de operar. Se conservan citas, clientes y el historial del negocio.</p></div>
        <div className="flex gap-2"><Button variant="outline" onClick={() => setConfirmSuspend(false)}>Cancelar</Button><Button variant="danger" isLoading={saving} onClick={() => void setActive(false)}>Confirmar suspensión</Button></div>
      </CardContent></Card>}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.8fr)]">
        <Card className="border-border/70 shadow-sm">
          <CardContent className="p-5 md:p-6">
            <div className="mb-5 flex items-center gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary"><Building2 className="h-5 w-5" aria-hidden="true" /></div><div><h2 className="font-semibold">Información del negocio</h2><p className="text-xs text-muted-foreground">Datos operativos visibles para administración</p></div></div>
            <dl className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
              <div><dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Acceso del negocio</dt><dd className="mt-2"><StatusBadge active={business.is_active} label={business.is_active ? 'Habilitado' : 'Suspendido'} /></dd></div>
              <div><dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Alta del negocio</dt><dd className="mt-2 flex items-center gap-2 text-sm">{business.onboarding_complete && <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden="true" />}{business.onboarding_complete ? 'Completada' : 'Pendiente'}</dd></div>
              <div><dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Dueño</dt><dd className="mt-2 break-all text-sm">{business.owner_email ?? 'Sin dueño asociado'}</dd></div>
              <div><dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Estado de acceso del dueño</dt><dd className="mt-2 text-sm">{business.owner_id == null ? 'Sin usuario asociado' : business.owner_is_active ? 'Cuenta habilitada' : 'Cuenta desactivada'}</dd></div>
              <div><dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Fecha de creación</dt><dd className="mt-2 text-sm">{formatDate(business.created_at)}</dd></div>
            </dl>
          </CardContent>
        </Card>

        <Card className="border-border/70 shadow-sm">
          <CardContent className="p-5 md:p-6">
            <h2 className="font-semibold">Acceso y datos</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">Suspender bloquea la operación del negocio para el dueño, incluso si mantiene una sesión abierta. Reactivar restablece ese acceso. Ninguna acción elimina registros.</p>
            <Link to="/admin/audit" className="mt-5 inline-flex text-sm font-semibold text-primary hover:underline">Consultar actividad administrativa</Link>
          </CardContent>
        </Card>
      </div>
    </>}
  </>
}
