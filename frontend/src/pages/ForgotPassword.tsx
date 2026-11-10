import { FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, CheckCircle2 } from 'lucide-react'
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from '@/components/ui'
import { authAPI } from '@/services/api'
import BrandMark from '@/components/BrandMark'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await authAPI.requestPasswordReset(email.trim())
      setSubmitted(true)
    } catch (cause) {
      const status = (cause as { response?: { status?: number } })?.response?.status
      setError(status === 429
        ? 'Se alcanzó el límite de solicitudes. Espera un momento antes de intentarlo de nuevo.'
        : 'No se pudo procesar la solicitud ahora. Inténtalo de nuevo más tarde.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
      <Card className="w-full max-w-lg">
        <CardHeader className="space-y-3 text-center">
          {submitted ? (
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <CheckCircle2 aria-hidden="true" />
            </div>
          ) : <BrandMark size={48} className="mx-auto rounded-xl" />}
          <CardTitle>{submitted ? 'Revisa tu correo' : 'Recupera tu contraseña'}</CardTitle>
        </CardHeader>
        <CardContent>
          {submitted ? (
            <div className="space-y-5 text-center">
              <p role="status" className="text-sm text-muted-foreground">
                Si existe una cuenta asociada a <strong className="break-all">{email}</strong>, recibirás un enlace para cambiar la contraseña. Puede tardar unos minutos.
              </p>
              <Link to="/login" className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline">
                <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Volver al acceso
              </Link>
              <div><Link to="/admin/login" className="text-sm font-medium text-primary hover:underline">Acceso de administración</Link></div>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-5">
              <p className="text-sm text-muted-foreground">
                Escribe el correo de acceso. Si está asociado a una cuenta, enviaremos un enlace válido durante una hora.
              </p>
              {error && <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}
              <Input
                label="Correo electrónico"
                type="email"
                autoComplete="email"
                required
                maxLength={320}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="tu@correo.com"
              />
              <Button type="submit" className="w-full" isLoading={busy}>Enviar enlace</Button>
              <div className="text-center">
                <Link to="/login" className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline">
                  <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Volver al acceso
                </Link>
                <div><Link to="/admin/login" className="text-sm font-medium text-primary hover:underline">Acceso de administración</Link></div>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </main>
  )
}
