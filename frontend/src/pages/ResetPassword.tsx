import { FormEvent, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, XCircle } from 'lucide-react'
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from '@/components/ui'
import { authAPI } from '@/services/api'
import BrandMark from '@/components/BrandMark'

type ResetState = 'loading' | 'form' | 'success' | 'invalid'

function removeFragmentAndReadToken(): string {
  const token = new URLSearchParams(window.location.hash.slice(1)).get('token') || ''
  if (window.location.hash) {
    window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`)
  }
  return token
}

export default function ResetPassword() {
  const [token, setToken] = useState('')
  const [state, setState] = useState<ResetState>('loading')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const consumedFragment = useRef(false)

  useEffect(() => {
    if (consumedFragment.current) return
    consumedFragment.current = true
    const value = removeFragmentAndReadToken()
    setToken(value)
    setState(value ? 'form' : 'invalid')
  }, [])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    if (password !== confirmation) {
      setError('Las contraseñas no coinciden.')
      return
    }
    setBusy(true)
    try {
      await authAPI.confirmPasswordReset(token, password)
      setState('success')
    } catch {
      setState('invalid')
    } finally {
      setBusy(false)
    }
  }

  const success = state === 'success'
  const invalid = state === 'invalid'
  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
      <Card className="w-full max-w-lg">
        <CardHeader className="space-y-3 text-center">
          {success || invalid ? (
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
              {success ? <CheckCircle2 aria-hidden="true" /> : <XCircle aria-hidden="true" />}
            </div>
          ) : <BrandMark size={48} className="mx-auto rounded-xl" />}
          <CardTitle>{success ? 'Contraseña actualizada' : invalid ? 'Enlace no válido o vencido' : state === 'loading' ? 'Validando enlace' : 'Define una nueva contraseña'}</CardTitle>
        </CardHeader>
        <CardContent>
          {state === 'loading' ? (
            <p role="status" className="py-4 text-center text-sm text-muted-foreground">Preparando el formulario…</p>
          ) : success ? (
            <div className="space-y-5 text-center">
              <p role="status" className="text-sm text-muted-foreground">Tu contraseña se actualizó. Inicia sesión con la nueva contraseña para continuar.</p>
              <Link to="/login" className="inline-flex w-full items-center justify-center rounded-lg bg-primary px-5 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
                Acceso de negocio
              </Link>
              <Link to="/admin/login" className="text-sm font-medium text-primary hover:underline">Acceso de administración</Link>
            </div>
          ) : invalid ? (
            <div className="space-y-5 text-center">
              <p className="text-sm text-muted-foreground">El enlace pudo haber vencido, ya se usó o no ser válido. Solicita uno nuevo para cambiar tu contraseña.</p>
              <Link to="/forgot-password" className="inline-flex w-full items-center justify-center rounded-lg bg-primary px-5 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
                Solicitar otro enlace
              </Link>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-5">
              <p className="text-sm text-muted-foreground">Elige una contraseña de 12 a 72 caracteres. El enlace de recuperación solo se puede usar una vez y vence en una hora.</p>
              {error && <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}
              <Input label="Nueva contraseña" type="password" autoComplete="new-password" minLength={12} maxLength={72} required value={password} onChange={(event) => setPassword(event.target.value)} />
              <Input label="Confirmar contraseña" type="password" autoComplete="new-password" minLength={12} maxLength={72} required value={confirmation} onChange={(event) => setConfirmation(event.target.value)} />
              <Button type="submit" className="w-full" isLoading={busy}>Guardar contraseña</Button>
            </form>
          )}
        </CardContent>
      </Card>
    </main>
  )
}
