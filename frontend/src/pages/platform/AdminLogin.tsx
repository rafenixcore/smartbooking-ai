import { FormEvent, useEffect, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from '@/components/ui'
import { usePlatformAuthStore } from '@/store/platformAuthStore'
import BrandMark from '@/components/BrandMark'

export default function AdminLogin() {
  const navigate = useNavigate()
  const { admin, ready, busy, initialize, login } = usePlatformAuthStore()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!ready) void initialize()
  }, [ready, initialize])

  if (ready && admin) return <Navigate to="/admin" replace />

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    try {
      await login(email.trim(), password)
      navigate('/admin', { replace: true })
    } catch {
      setError('No se pudo iniciar sesión. Revisa el correo y la contraseña.')
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/10 via-background to-muted/50 px-4 py-10">
      <div className="w-full max-w-md space-y-7">
        <header className="text-center">
          <BrandMark size={56} className="mx-auto mb-4 rounded-2xl shadow-lg shadow-primary/20" />
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Rafenixcore</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight">Administración</h1>
          <p className="mt-2 text-sm text-muted-foreground">Acceso privado a SmartBooking</p>
        </header>

        <Card className="border-border/70 shadow-xl shadow-foreground/5">
          <CardHeader>
            <CardTitle>Inicia sesión</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-5" onSubmit={submit}>
              {error && <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}
              <Input label="Correo administrador" type="email" autoComplete="username" required maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} />
              <Input label="Contraseña" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
              <Button type="submit" className="w-full" disabled={!ready} isLoading={busy}>
                Entrar al panel <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Button>
              <div className="text-center">
                <Link to="/forgot-password" className="text-sm font-medium text-primary hover:underline">¿Olvidaste tu contraseña?</Link>
              </div>
            </form>
          </CardContent>
        </Card>
        <p className="text-center text-xs text-muted-foreground">Acceso solo para administradores de la plataforma.</p>
      </div>
    </main>
  )
}
