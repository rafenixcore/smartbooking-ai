import { FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from '@/components/ui'
import { useAuthStore } from '@/store/authStore'
import { useBusinessStore } from '@/store/businessStore'
import BrandMark from '@/components/BrandMark'

export default function Login() {
  const navigate = useNavigate()
  const { login, isLoading, error } = useAuthStore()
  const { fetchBusinesses } = useBusinessStore()
  const [credentials, setCredentials] = useState({ email: '', password: '' })

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    try {
      await login(credentials)
      await fetchBusinesses()
      navigate('/dashboard')
    } catch {
      // El store ya expone el mensaje de error para esta pantalla.
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
      <div className="w-full max-w-md space-y-6">
        <header className="text-center">
          <BrandMark size={56} className="mx-auto mb-4 rounded-2xl shadow-sm" />
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">Rafenixcore</p>
          <h1 className="mt-3 text-3xl font-bold tracking-tight text-foreground">SmartBooking</h1>
          <p className="mt-2 text-sm text-muted-foreground">Agenda y gestiona las citas de tu negocio.</p>
        </header>

        <Card className="border-border/70 shadow-lg shadow-foreground/5">
          <CardHeader>
            <CardTitle>Iniciar sesión</CardTitle>
            <p className="text-sm text-muted-foreground">Usa el correo de la invitación y tu contraseña.</p>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-5">
              {error && <p role="alert" className="rounded-control border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{error}</p>}
              <Input
                label="Correo electrónico"
                name="email"
                type="email"
                autoComplete="username"
                maxLength={320}
                required
                value={credentials.email}
                onChange={(event) => setCredentials((current) => ({ ...current, email: event.target.value }))}
                placeholder="tu@negocio.com"
              />
              <Input
                label="Contraseña"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={credentials.password}
                onChange={(event) => setCredentials((current) => ({ ...current, password: event.target.value }))}
                placeholder="Tu contraseña"
              />
              <div className="text-right">
                <Link to="/forgot-password" className="text-sm font-medium text-primary hover:underline">¿Olvidaste tu contraseña?</Link>
              </div>
              <Button type="submit" className="w-full" isLoading={isLoading}>Entrar a mi cuenta</Button>
              <p className="text-center text-sm leading-6 text-muted-foreground">¿Eres nuevo? El administrador te enviará una invitación por correo.</p>
            </form>
          </CardContent>
        </Card>

        <footer className="text-center text-xs text-muted-foreground">© {new Date().getFullYear()} SmartBooking · Rafenixcore</footer>
      </div>
    </main>
  )
}
