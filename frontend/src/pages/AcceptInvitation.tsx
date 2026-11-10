import { FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from '@/components/ui'
import { authAPI } from '@/services/api'
import BrandMark from '@/components/BrandMark'

type InvitationState = 'loading' | 'ready' | 'invalid' | 'accepted'

export default function AcceptInvitation() {
  const [token] = useState(() => {
    const value = new URLSearchParams(window.location.hash.slice(1)).get('token') || ''
    if (value) {
      window.history.replaceState(
        window.history.state,
        '',
        `${window.location.pathname}${window.location.search}`
      )
    }
    return value
  })
  const navigate = useNavigate()
  const [state, setState] = useState<InvitationState>('loading')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    let cancelled = false
    if (!token) {
      setState('invalid')
      return
    }
    authAPI.getInvitation(token).then(
      (invitation) => {
        if (!cancelled) {
          setEmail(invitation.email)
          setState('ready')
        }
      },
      () => {
        if (!cancelled) setState('invalid')
      }
    )
    return () => {
      cancelled = true
    }
  }, [token])

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    if (password !== confirmation) {
      setError('Las contraseñas no coinciden.')
      return
    }
    setIsSubmitting(true)
    try {
      await authAPI.acceptInvitation(token, password)
      setState('accepted')
    } catch (cause) {
      const detail = (cause as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'No se pudo aceptar la invitación.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
      <Card className="w-full max-w-lg">
        <CardHeader className="space-y-3 text-center">
          {state === 'accepted' || state === 'invalid' ? (
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
              {state === 'accepted' ? <CheckCircle2 aria-hidden="true" /> : <XCircle aria-hidden="true" />}
            </div>
          ) : <BrandMark size={48} className="mx-auto rounded-xl" />}
          <CardTitle>
            {state === 'accepted' ? 'Invitación aceptada' : 'Activa tu acceso a SmartBooking'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {state === 'loading' && (
            <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground" role="status">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              Validando invitación…
            </div>
          )}

          {state === 'invalid' && (
            <div className="space-y-4 text-center">
              <XCircle className="mx-auto h-10 w-10 text-destructive" aria-hidden="true" />
              <p className="text-sm text-muted-foreground">
                Este enlace no es válido o venció. Pide al administrador que te envíe otra invitación.
              </p>
              <Button type="button" variant="outline" onClick={() => navigate('/login')}>
                Ir al acceso
              </Button>
            </div>
          )}

          {state === 'ready' && (
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="rounded-lg border border-border bg-muted/40 p-4">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Correo de acceso</p>
                <p className="mt-1 break-all font-medium text-foreground">{email}</p>
              </div>
              <p className="text-sm text-muted-foreground">
                Define una contraseña para aceptar la invitación. Después iniciarás sesión y completarás la información del negocio.
              </p>
              {error && (
                <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                  {error}
                </p>
              )}
              <Input
                label="Contraseña"
                type="password"
                autoComplete="new-password"
                minLength={12}
                maxLength={72}
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
              <Input
                label="Confirmar contraseña"
                type="password"
                autoComplete="new-password"
                minLength={12}
                maxLength={72}
                required
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
              />
              <Button type="submit" className="w-full" isLoading={isSubmitting}>
                Aceptar invitación
              </Button>
            </form>
          )}

          {state === 'accepted' && (
            <div className="space-y-4 text-center">
              <p className="text-sm text-muted-foreground">
                Tu contraseña quedó configurada para <strong>{email}</strong>. Inicia sesión para completar el alta de tu negocio.
              </p>
              <Link
                className="inline-flex w-full items-center justify-center rounded-lg bg-primary px-5 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                to="/login"
                state={{ invitedEmail: email }}
              >
                Iniciar sesión
              </Link>
            </div>
          )}
        </CardContent>
      </Card>
    </main>
  )
}
