import { FormEvent, useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Building2, CheckCircle2, MessageCircle, PauseCircle, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { ConfirmationModal } from '@/components/ui/ConfirmationModal'
import { Input } from '@/components/ui/Input'
import { platformAPI } from '@/services/api'
import type { PlatformBusiness, PlatformWhatsAppConfig } from '@/types/platform'
import { ErrorState, LoadingState, PageHeading, StatusBadge } from './AdminShared'
import { formatDate } from './platformUtils'

const ID_MIN_LENGTH = 5
const ID_MAX_LENGTH = 64

function validateWhatsAppCredentials(phone: string, waba: string): string | null {
  if (!phone && !waba) return null
  if (!phone || !waba) {
    return 'Completa ambos campos: Phone Number ID y WABA ID, o deja ambos vacíos para quitar la configuración.'
  }
  if (!/^[0-9]+$/.test(phone)) {
    return 'El Phone Number ID debe contener solo números.'
  }
  if (!/^[0-9]+$/.test(waba)) {
    return 'El WABA ID debe contener solo números.'
  }
  if (phone.length < ID_MIN_LENGTH || phone.length > ID_MAX_LENGTH) {
    return `El Phone Number ID debe tener entre ${ID_MIN_LENGTH} y ${ID_MAX_LENGTH} dígitos.`
  }
  if (waba.length < ID_MIN_LENGTH || waba.length > ID_MAX_LENGTH) {
    return `El WABA ID debe tener entre ${ID_MIN_LENGTH} y ${ID_MAX_LENGTH} dígitos.`
  }
  return null
}

function getWhatsAppErrorMessage(error: unknown): string {
  const response = (error as {
    response?: { status?: number; data?: { detail?: unknown } }
  })?.response
  const detail = response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown } | undefined
    if (typeof first?.msg === 'string') {
      return first.msg.replace(/^Value error,\s*/i, '')
    }
  }
  if (response?.status === 409) {
    return 'Ese Phone Number ID ya está vinculado a otro negocio. Quítalo de ese negocio o usa otro.'
  }
  if (response?.status === 401 || response?.status === 403) {
    return 'Tu sesión expiró. Vuelve a iniciar sesión.'
  }
  if (!response) {
    return 'No se pudo conectar con el servidor. Revisa tu conexión.'
  }
  if (response.status === 422) {
    return `Revisa los campos: ambos IDs deben ser numéricos y tener entre ${ID_MIN_LENGTH} y ${ID_MAX_LENGTH} dígitos.`
  }
  return 'No se pudieron guardar las credenciales. Inténtalo de nuevo.'
}

export default function AdminBusinessDetail() {
  const { businessId } = useParams()
  const parsedId = Number(businessId)
  const [business, setBusiness] = useState<PlatformBusiness | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [confirmSuspend, setConfirmSuspend] = useState(false)
  const [error, setError] = useState('')
  const [whatsAppConfig, setWhatsAppConfig] = useState<PlatformWhatsAppConfig | null>(null)
  const [whatsAppForm, setWhatsAppForm] = useState({ whatsapp_phone_number_id: '', waba_id: '' })
  const [savedWhatsAppForm, setSavedWhatsAppForm] = useState({ whatsapp_phone_number_id: '', waba_id: '' })
  const [whatsAppSaving, setWhatsAppSaving] = useState(false)
  const [whatsAppError, setWhatsAppError] = useState('')
  const [confirmClearWhatsApp, setConfirmClearWhatsApp] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      if (!Number.isSafeInteger(parsedId) || parsedId < 1) throw new Error('invalid id')
      setBusiness(await platformAPI.getBusiness(parsedId))
      const channel = await platformAPI.getWhatsAppConfig(parsedId)
      setWhatsAppConfig(channel)
      const nextForm = {
        whatsapp_phone_number_id: channel.whatsapp_phone_number_id || '',
        waba_id: channel.waba_id || '',
      }
      setWhatsAppForm(nextForm)
      setSavedWhatsAppForm(nextForm)
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

  const isWhatsAppDirty =
    whatsAppForm.whatsapp_phone_number_id.trim() !== savedWhatsAppForm.whatsapp_phone_number_id.trim() ||
    whatsAppForm.waba_id.trim() !== savedWhatsAppForm.waba_id.trim()

  const persistWhatsAppCredentials = async (phone: string, waba: string) => {
    if (!business) return
    setWhatsAppSaving(true)
    setWhatsAppError('')
    try {
      const updated = await platformAPI.updateWhatsAppConfig(business.id, {
        whatsapp_phone_number_id: phone || null,
        waba_id: waba || null,
      })
      setWhatsAppConfig(updated)
      const nextForm = {
        whatsapp_phone_number_id: updated.whatsapp_phone_number_id || '',
        waba_id: updated.waba_id || '',
      }
      setWhatsAppForm(nextForm)
      setSavedWhatsAppForm(nextForm)
    } catch (error) {
      setWhatsAppError(getWhatsAppErrorMessage(error))
    } finally {
      setWhatsAppSaving(false)
      setConfirmClearWhatsApp(false)
    }
  }

  const saveWhatsAppConfig = async (event: FormEvent) => {
    event.preventDefault()
    if (!business || !isWhatsAppDirty) return
    const phone = whatsAppForm.whatsapp_phone_number_id.trim()
    const waba = whatsAppForm.waba_id.trim()
    const validationError = validateWhatsAppCredentials(phone, waba)
    if (validationError) {
      setWhatsAppError(validationError)
      return
    }
    const hadSavedCredentials = Boolean(
      savedWhatsAppForm.whatsapp_phone_number_id || savedWhatsAppForm.waba_id
    )
    if (!phone && !waba && hadSavedCredentials) {
      setConfirmClearWhatsApp(true)
      return
    }
    await persistWhatsAppCredentials(phone, waba)
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

      <Card className="border-border/70 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageCircle className="h-5 w-5 text-primary" aria-hidden="true" />
            WhatsApp del negocio
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Registra primero el número en Meta y completa su verificación. Después asigna aquí los identificadores. El WABA puede repetirse entre negocios; cada Phone Number ID debe ser único.
          </p>
          {whatsAppConfig && <div className="text-sm" role="status">
            {whatsAppConfig.status === 'ids_saved' ? 'Credenciales guardadas' : 'WhatsApp sin configurar'}
            {' · '}
            {whatsAppConfig.credentials_configured
              ? 'Credenciales Meta disponibles en el backend'
              : 'Faltan credenciales Meta en el backend'}
          </div>}
          {whatsAppError && <ErrorState message={whatsAppError} />}
          <form onSubmit={(event) => void saveWhatsAppConfig(event)} className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <Input
                label="Phone Number ID"
                value={whatsAppForm.whatsapp_phone_number_id}
                onChange={(event) => {
                  setWhatsAppForm({ ...whatsAppForm, whatsapp_phone_number_id: event.target.value })
                  setWhatsAppError('')
                }}
                maxLength={ID_MAX_LENGTH}
                autoComplete="off"
              />
              <Input
                label="WABA ID"
                value={whatsAppForm.waba_id}
                onChange={(event) => {
                  setWhatsAppForm({ ...whatsAppForm, waba_id: event.target.value })
                  setWhatsAppError('')
                }}
                maxLength={ID_MAX_LENGTH}
                autoComplete="off"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Completa ambos campos o deja ambos vacíos para quitar la configuración.
              Solo números, entre {ID_MIN_LENGTH} y {ID_MAX_LENGTH} dígitos.
            </p>
            <div className="flex items-center justify-end gap-3">
              {!isWhatsAppDirty && <span className="text-xs text-muted-foreground">Sin cambios</span>}
              <Button type="submit" isLoading={whatsAppSaving} disabled={!isWhatsAppDirty}>
                Guardar credenciales
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </>}
    <ConfirmationModal
      isOpen={confirmClearWhatsApp}
      onClose={() => setConfirmClearWhatsApp(false)}
      onConfirm={() => void persistWhatsAppCredentials('', '')}
      title="¿Quitar credenciales de WhatsApp?"
      message="El negocio dejará de recibir y enviar mensajes por WhatsApp hasta que vuelvas a configurar sus credenciales."
      confirmText="Sí, quitar credenciales"
      cancelText="Cancelar"
      isLoading={whatsAppSaving}
    />
  </>
}
