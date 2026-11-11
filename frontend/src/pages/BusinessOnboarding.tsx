import { FormEvent, useEffect, useState } from 'react'
import { Building2, MapPin, Phone, Store } from 'lucide-react'
import { toast } from 'sonner'
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from '@/components/ui'
import { useBusinessStore } from '@/store/businessStore'
import type { BusinessFormData } from '@/types'

type BusinessOnboardingProps = {
  compact?: boolean
  onCreated?: () => void
}

export default function BusinessOnboarding({ compact = false, onCreated }: BusinessOnboardingProps) {
  const { currentBusiness, createBusiness, updateBusiness, isLoading } = useBusinessStore()
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState<BusinessFormData>({
    name: '',
    phone: '',
    description: '',
    address: '',
  })

  useEffect(() => {
    if (currentBusiness && !currentBusiness.onboarding_completed_at) {
      setForm({
        name: currentBusiness.name || '',
        phone: currentBusiness.phone || '',
        description: currentBusiness.description || '',
        address: currentBusiness.address || '',
      })
    }
  }, [currentBusiness])

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)

    try {
      // La ubicación y la descripción son opcionales durante el alta.
      const profile = {
        name: form.name.trim(),
        phone: form.phone.trim(),
        description: form.description?.trim() || undefined,
        address: form.address?.trim() || undefined,
      }
      if (currentBusiness) {
        await updateBusiness(currentBusiness.id, profile)
      } else {
        await createBusiness(profile)
      }
      toast.success('Información del negocio guardada')
      onCreated?.()
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'No se pudo crear el negocio')
    }
  }

  return (
    <div className={compact ? '' : 'min-h-full flex items-center justify-center px-4 py-8'}>
      <div className="w-full max-w-3xl space-y-6">
        {!compact && (
          <div className="text-center space-y-3">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Store className="h-7 w-7" />
            </div>
            <div>
                <h1 className="text-3xl font-bold text-foreground">
                {currentBusiness ? 'Completa el perfil de tu negocio' : 'Registra tu negocio'}
              </h1>
              <p className="mt-2 text-muted-foreground">
                Completa los datos principales para continuar al panel y administrar tus citas.
              </p>
            </div>
          </div>
        )}

        {compact ? null : (
          <Card>
            <CardHeader>
              <CardTitle>Datos principales</CardTitle>
            </CardHeader>
            <CardContent>
              <BusinessForm
                form={form}
                setForm={setForm}
                error={error}
                isLoading={isLoading}
                submitLabel={currentBusiness ? 'Completar alta' : 'Crear negocio'}
                onSubmit={handleSubmit}
              />
            </CardContent>
          </Card>
        )}

        {compact && (
          <BusinessForm
            form={form}
            setForm={setForm}
            error={error}
            isLoading={isLoading}
            submitLabel={currentBusiness ? 'Completar alta' : 'Crear negocio'}
            onSubmit={handleSubmit}
          />
        )}
      </div>
    </div>
  )
}

type BusinessFormProps = {
  form: BusinessFormData
  setForm: (form: BusinessFormData) => void
  error: string | null
  isLoading: boolean
  submitLabel: string
  onSubmit: (event: FormEvent) => void
}

function BusinessForm({
  form,
  setForm,
  error,
  isLoading,
  submitLabel,
  onSubmit,
}: BusinessFormProps) {
  return (
    <form onSubmit={onSubmit} className="space-y-5">
      {error && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm font-medium text-destructive">
          {error}
        </div>
      )}

      <div className="grid gap-5 md:grid-cols-2">
        <Input
          label="Nombre del negocio"
          required
          value={form.name}
          onChange={(event) => setForm({ ...form, name: event.target.value })}
          placeholder="Ej. Mi negocio"
        />
        <Input
          label="Teléfono del negocio"
          required
          value={form.phone}
          onChange={(event) => setForm({ ...form, phone: event.target.value })}
          placeholder="Ej. 8095551234"
        />
      </div>

      <Input
        label="Dirección"
        value={form.address}
        onChange={(event) => setForm({ ...form, address: event.target.value })}
        placeholder="Opcional"
      />

      <div>
        <label className="mb-2 block text-sm font-semibold text-foreground">
          Descripción
        </label>
        <textarea
          value={form.description}
          onChange={(event) => setForm({ ...form, description: event.target.value })}
          rows={4}
          className="flex w-full rounded-control border border-input bg-background px-3 py-3 text-sm transition-colors placeholder:text-muted-foreground hover:border-primary/40 focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25"
          placeholder="Opcional. Describe tus servicios y cualquier información útil para tus clientes."
        />
      </div>

      <div className="grid gap-3 rounded-lg border border-border/50 bg-muted/30 p-4 text-sm text-muted-foreground md:grid-cols-3">
        <div className="flex items-center gap-2">
          <Building2 className="h-4 w-4 text-primary" />
          Panel por negocio
        </div>
        <div className="flex items-center gap-2">
          <Phone className="h-4 w-4 text-primary" />
          Citas y clientes
        </div>
      </div>

      <div className="flex justify-end">
        <Button type="submit" size="lg" isLoading={isLoading}>
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}
