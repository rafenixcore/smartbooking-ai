import { FormEvent, useCallback, useEffect, useState } from 'react'
import { MailPlus, RefreshCw, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { platformAPI } from '@/services/api'
import type { PlatformInvitation, PlatformInvitationPage } from '@/types/platform'
import { EmptyState, ErrorState, InvitationBadge, LoadingState, PageHeading } from './AdminShared'
import { formatDate } from './platformUtils'

const PAGE_SIZE = 10

export default function AdminInvitations() {
  const [page, setPage] = useState<PlatformInvitationPage | null>(null)
  const [offset, setOffset] = useState(0)
  const [status, setStatus] = useState<'all' | PlatformInvitation['status']>('all')
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [workingId, setWorkingId] = useState<number | null>(null)
  const [confirmId, setConfirmId] = useState<number | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setPage(await platformAPI.listInvitations({
        offset,
        limit: PAGE_SIZE,
        status: status === 'all' ? undefined : status,
      }))
    } catch {
      setError('No fue posible cargar las invitaciones.')
    } finally {
      setLoading(false)
    }
  }, [offset, status])

  useEffect(() => { void load() }, [load])

  const create = async (event: FormEvent) => {
    event.preventDefault()
    setCreating(true)
    setMessage('')
    setError('')
    try {
      const invitation = await platformAPI.createInvitation(email.trim())
      setEmail('')
      setOffset(0)
      setStatus('all')
      setMessage(invitation.delivery_status === 'sent'
        ? `Resend aceptó el envío a ${invitation.email}. La persona invitada puede revisar su correo y la carpeta de spam.`
        : `La invitación para ${invitation.email} quedó creada, pero el correo no se pudo enviar. Puedes reintentarlo desde la lista.`)
      setPage(await platformAPI.listInvitations({ offset: 0, limit: PAGE_SIZE }))
    } catch (cause) {
      const statusCode = (cause as { response?: { status?: number } })?.response?.status
      setError(statusCode === 409 ? 'Ya existe una cuenta o invitación pendiente para ese correo.' : 'No se pudo crear la invitación. Revisa el correo e inténtalo otra vez.')
    } finally {
      setCreating(false)
    }
  }

  const resend = async (invitationId: number) => {
    setWorkingId(invitationId)
    setMessage('')
    setError('')
    try {
      const invitation = await platformAPI.resendInvitation(invitationId)
      setMessage(invitation.delivery_status === 'sent' ? `Resend aceptó el reenvío a ${invitation.email}.` : `El enlace se renovó, pero Resend no aceptó el correo para ${invitation.email}.`)
      await load()
    } catch {
      setError('No se pudo reenviar esta invitación.')
    } finally {
      setWorkingId(null)
    }
  }

  const revoke = async (invitationId: number) => {
    setWorkingId(invitationId)
    setError('')
    setMessage('')
    try {
      const invitation = await platformAPI.revokeInvitation(invitationId)
      setConfirmId(null)
      setMessage(`Se revocó la invitación de ${invitation.email}.`)
      await load()
    } catch {
      setError('No se pudo revocar esta invitación.')
    } finally {
      setWorkingId(null)
    }
  }

  return <>
    <PageHeading title="Invitaciones" description="Invita a cada dueño por correo. Su dirección será su usuario y solo tendrá que definir una contraseña." />

    <Card className="mb-5 border-border/70 shadow-sm">
      <CardContent className="p-4 md:p-5">
        <form onSubmit={create} className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
          <Input label="Correo del dueño" type="email" autoComplete="email" maxLength={320} required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="dueno@negocio.com" />
          <Button type="submit" isLoading={creating}><MailPlus className="h-4 w-4" aria-hidden="true" /> Enviar invitación</Button>
        </form>
        <p className="mt-3 text-xs leading-5 text-muted-foreground">El enlace vence en 72 horas. Después de definir su contraseña, el dueño completará la información del negocio.</p>
      </CardContent>
    </Card>

    {message && <p role="status" className="mb-4 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-foreground">{message}</p>}
    {error && <div className="mb-4"><ErrorState message={error} /></div>}

    <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <h2 className="font-semibold">Historial de invitaciones</h2>
      <Select label="Filtrar por estado" value={status} onChange={(event) => { setStatus(event.target.value as typeof status); setOffset(0) }} className="sm:max-w-xs" options={[
        { value: 'all', label: 'Todas' }, { value: 'pending', label: 'Pendientes' },
        { value: 'accepted', label: 'Aceptadas' }, { value: 'expired', label: 'Vencidas' }, { value: 'revoked', label: 'Revocadas' },
      ]} />
    </div>

    {loading ? <LoadingState label="Cargando invitaciones…" /> : error && !page ? <ErrorState message={error} onRetry={() => void load()} /> : !page || page.items.length === 0 ? (
      <EmptyState title="No hay invitaciones en esta vista" description="Cuando invites a un dueño, podrás consultar aquí su estado y el resultado del envío." />
    ) : <>
      <Card className="overflow-hidden border-border/70 shadow-sm">
        <Table>
          <TableHeader><TableRow><TableHead>Correo</TableHead><TableHead>Estado</TableHead><TableHead>Enlace vence</TableHead><TableHead>Creada</TableHead><TableHead>Acciones</TableHead></TableRow></TableHeader>
          <TableBody>{page.items.map((invitation) => <TableRow key={invitation.id}>
            <TableCell className="max-w-64 break-all font-medium">{invitation.email}</TableCell>
            <TableCell><InvitationBadge status={invitation.status} delivery={invitation.delivery_status} /></TableCell>
            <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{formatDate(invitation.expires_at)}</TableCell>
            <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{formatDate(invitation.created_at)}</TableCell>
            <TableCell><div className="flex flex-wrap gap-2">
              {(invitation.status === 'pending' || invitation.status === 'expired') && <Button size="sm" variant="outline" isLoading={workingId === invitation.id} onClick={() => void resend(invitation.id)}><RefreshCw className="h-3.5 w-3.5" aria-hidden="true" /> Reenviar</Button>}
              {invitation.status === 'pending' && (confirmId === invitation.id
                ? <><Button size="sm" variant="danger" isLoading={workingId === invitation.id} onClick={() => void revoke(invitation.id)}>Confirmar revocación</Button><Button size="sm" variant="ghost" aria-label="Cancelar revocación" onClick={() => setConfirmId(null)}><X className="h-4 w-4" aria-hidden="true" /></Button></>
                : <Button size="sm" variant="ghost" onClick={() => setConfirmId(invitation.id)}>Revocar</Button>)}
            </div></TableCell>
          </TableRow>)}</TableBody>
        </Table>
      </Card>
      <div className="mt-4 flex flex-col gap-3 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <p>Mostrando {offset + 1}–{Math.min(offset + page.items.length, page.total)} de {page.total}</p>
        <div className="flex gap-2"><Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Anterior</Button><Button variant="outline" size="sm" disabled={offset + PAGE_SIZE >= page.total} onClick={() => setOffset(offset + PAGE_SIZE)}>Siguiente</Button></div>
      </div>
    </>}
  </>
}
