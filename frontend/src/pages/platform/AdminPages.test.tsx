import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AdminRoutes from './AdminRoutes'
import AdminOverview from './AdminOverview'
import AdminBusinesses from './AdminBusinesses'
import AdminBusinessDetail from './AdminBusinessDetail'
import AdminInvitations from './AdminInvitations'
import { platformAPI } from '@/services/api'

const authState = vi.hoisted(() => ({
  value: {
    admin: null as { id: number; email: string } | null,
    ready: true,
    initialize: vi.fn(),
    logout: vi.fn(),
  },
}))

vi.mock('@/services/api', () => ({
  platformAPI: {
    listBusinesses: vi.fn(),
    getBusiness: vi.fn(),
    getWhatsAppConfig: vi.fn(),
    updateWhatsAppConfig: vi.fn(),
    setBusinessActive: vi.fn(),
    listInvitations: vi.fn(),
    createInvitation: vi.fn(),
    resendInvitation: vi.fn(),
    revokeInvitation: vi.fn(),
    listAudit: vi.fn(),
  },
}))

vi.mock('@/store/platformAuthStore', () => ({
  usePlatformAuthStore: () => authState.value,
}))

const emptyBusinesses = { items: [], total: 0, offset: 0, limit: 10 }
const emptyInvitations = { items: [], total: 0, offset: 0, limit: 10 }
const detailBusiness = {
  id: 41, name: 'Estudio Norte', is_active: true, onboarding_complete: true,
  owner_id: 9, owner_email: 'owner@example.test', owner_is_active: true,
  created_at: '2026-11-01T10:00:00Z',
}

function renderBusinessDetail() {
  return render(
    <MemoryRouter initialEntries={['/admin/businesses/41']}>
      <Routes><Route path="/admin/businesses/:businessId" element={<AdminBusinessDetail />} /></Routes>
    </MemoryRouter>
  )
}

describe('platform administration screens', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authState.value = { admin: null, ready: true, initialize: vi.fn(), logout: vi.fn() }
    vi.mocked(platformAPI.listBusinesses).mockResolvedValue(emptyBusinesses)
    vi.mocked(platformAPI.listInvitations).mockResolvedValue(emptyInvitations)
    vi.mocked(platformAPI.listAudit).mockResolvedValue({ items: [], total: 0, offset: 0, limit: 6 })
    vi.mocked(platformAPI.getWhatsAppConfig).mockResolvedValue({
      business_id: 41, whatsapp_phone_number_id: null, waba_id: null,
      credentials_configured: true, status: 'unconfigured',
    })
  })

  it('sends an unauthenticated platform visit to the separate admin login', async () => {
    render(
      <MemoryRouter initialEntries={['/admin']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/admin/login" element={<div>Acceso administrativo</div>} />
          <Route path="/admin" element={<AdminRoutes />}><Route index element={<div>Resumen privado</div>} /></Route>
        </Routes>
      </MemoryRouter>
    )
    expect(await screen.findByText('Acceso administrativo')).toBeInTheDocument()
  })

  it('shows explicit empty states without inventing business or invitation data', async () => {
    render(<MemoryRouter><AdminBusinesses /></MemoryRouter>)
    expect(await screen.findByText('No encontramos negocios')).toBeInTheDocument()
    expect(platformAPI.listBusinesses).toHaveBeenCalledWith({ offset: 0, limit: 10, status: undefined, q: undefined })

    render(<MemoryRouter><AdminInvitations /></MemoryRouter>)
    expect(await screen.findByText('No hay invitaciones en esta vista')).toBeInTheDocument()
  })

  it('shows source-backed summary counts and clarifies that message costs are not available yet', async () => {
    vi.mocked(platformAPI.listBusinesses)
      .mockResolvedValueOnce({ ...emptyBusinesses, total: 7 })
      .mockResolvedValueOnce({ ...emptyBusinesses, total: 2 })
    vi.mocked(platformAPI.listInvitations).mockResolvedValue({ ...emptyInvitations, total: 3 })
    render(<MemoryRouter><AdminOverview /></MemoryRouter>)
    expect(await screen.findByText('7')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText(/no presenta estimaciones como gasto real/i)).toBeInTheDocument()
  })

  it('requires confirmation before suspension and displays the updated business state', async () => {
    vi.mocked(platformAPI.getBusiness).mockResolvedValue({
      id: 41, name: 'Estudio Norte', is_active: true, onboarding_complete: true,
      owner_id: 9, owner_email: 'owner@example.test', owner_is_active: true, created_at: '2026-11-01T10:00:00Z',
    })
    vi.mocked(platformAPI.setBusinessActive).mockResolvedValue({
      id: 41, name: 'Estudio Norte', is_active: false, onboarding_complete: true,
      owner_id: 9, owner_email: 'owner@example.test', owner_is_active: true, created_at: '2026-11-01T10:00:00Z',
    })
    render(
      <MemoryRouter initialEntries={['/admin/businesses/41']}>
        <Routes><Route path="/admin/businesses/:businessId" element={<AdminBusinessDetail />} /></Routes>
      </MemoryRouter>
    )
    fireEvent.click(await screen.findByRole('button', { name: /suspender negocio/i }))
    expect(screen.getByText(/¿suspender este negocio/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar suspensión' }))
    await waitFor(() => expect(platformAPI.setBusinessActive).toHaveBeenCalledWith(41, false))
    expect(await screen.findByText('Suspendido')).toBeInTheDocument()
  })

  it('lets only the platform admin configure WhatsApp credentials on the business detail', async () => {
    vi.mocked(platformAPI.getBusiness).mockResolvedValue(detailBusiness)
    vi.mocked(platformAPI.getWhatsAppConfig).mockResolvedValue({
      business_id: 41, whatsapp_phone_number_id: null, waba_id: null,
      credentials_configured: true, status: 'unconfigured',
    })
    vi.mocked(platformAPI.updateWhatsAppConfig).mockResolvedValue({
      business_id: 41, whatsapp_phone_number_id: '1180291398493188',
      waba_id: '2183193562429781', credentials_configured: true, status: 'ids_saved',
    })

    renderBusinessDetail()

    const saveButton = await screen.findByRole('button', { name: /guardar credenciales/i })
    expect(saveButton).toBeDisabled()

    const phoneId = screen.getByLabelText('Phone Number ID')
    const accountId = screen.getByLabelText('WABA ID')
    fireEvent.change(phoneId, { target: { value: '1180291398493188' } })
    fireEvent.change(accountId, { target: { value: '2183193562429781' } })
    expect(saveButton).toBeEnabled()
    fireEvent.click(saveButton)

    await waitFor(() => expect(platformAPI.updateWhatsAppConfig).toHaveBeenCalledWith(41, {
      whatsapp_phone_number_id: '1180291398493188', waba_id: '2183193562429781',
    }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Credenciales guardadas'))
    expect(saveButton).toBeDisabled()
  })

  it('allows clearing both WhatsApp credentials explicitly', async () => {
    vi.mocked(platformAPI.getBusiness).mockResolvedValue(detailBusiness)
    vi.mocked(platformAPI.getWhatsAppConfig).mockResolvedValue({
      business_id: 41, whatsapp_phone_number_id: '1180291398493188',
      waba_id: '2183193562429781', credentials_configured: true, status: 'ids_saved',
    })
    vi.mocked(platformAPI.updateWhatsAppConfig).mockResolvedValue({
      business_id: 41, whatsapp_phone_number_id: null, waba_id: null,
      credentials_configured: true, status: 'unconfigured',
    })
    renderBusinessDetail()

    const saveButton = await screen.findByRole('button', { name: /guardar credenciales/i })
    expect(saveButton).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Phone Number ID'), { target: { value: '' } })
    fireEvent.change(screen.getByLabelText('WABA ID'), { target: { value: '' } })
    expect(saveButton).toBeEnabled()
    fireEvent.click(saveButton)

    expect(await screen.findByText('¿Quitar credenciales de WhatsApp?')).toBeInTheDocument()
    expect(platformAPI.updateWhatsAppConfig).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Sí, quitar credenciales' }))

    await waitFor(() => expect(platformAPI.updateWhatsAppConfig).toHaveBeenCalledWith(41, {
      whatsapp_phone_number_id: null, waba_id: null,
    }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('WhatsApp sin configurar'))
    expect(saveButton).toBeDisabled()
  })

  it('keeps WhatsApp credentials when removal is cancelled', async () => {
    vi.mocked(platformAPI.getBusiness).mockResolvedValue(detailBusiness)
    vi.mocked(platformAPI.getWhatsAppConfig).mockResolvedValue({
      business_id: 41, whatsapp_phone_number_id: '1180291398493188',
      waba_id: '2183193562429781', credentials_configured: true, status: 'ids_saved',
    })
    renderBusinessDetail()

    const saveButton = await screen.findByRole('button', { name: /guardar credenciales/i })
    fireEvent.change(screen.getByLabelText('Phone Number ID'), { target: { value: '' } })
    fireEvent.change(screen.getByLabelText('WABA ID'), { target: { value: '' } })
    fireEvent.click(saveButton)

    expect(await screen.findByText('¿Quitar credenciales de WhatsApp?')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

    await waitFor(() =>
      expect(screen.queryByText('¿Quitar credenciales de WhatsApp?')).not.toBeInTheDocument()
    )
    expect(platformAPI.updateWhatsAppConfig).not.toHaveBeenCalled()
  })

  it('requires both WhatsApp credentials before saving', async () => {
    vi.mocked(platformAPI.getBusiness).mockResolvedValue(detailBusiness)
    renderBusinessDetail()

    fireEvent.change(await screen.findByLabelText('Phone Number ID'), {
      target: { value: '1180291398493188' },
    })
    fireEvent.click(screen.getByRole('button', { name: /guardar credenciales/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/Completa ambos campos/i)
    expect(platformAPI.updateWhatsAppConfig).not.toHaveBeenCalled()
  })

  it('rejects non-numeric WhatsApp credentials before calling the API', async () => {
    vi.mocked(platformAPI.getBusiness).mockResolvedValue(detailBusiness)
    renderBusinessDetail()

    fireEvent.change(await screen.findByLabelText('Phone Number ID'), {
      target: { value: 'phone-abc' },
    })
    fireEvent.change(screen.getByLabelText('WABA ID'), {
      target: { value: '2183193562429781' },
    })
    fireEvent.click(screen.getByRole('button', { name: /guardar credenciales/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/solo números/i)
    expect(platformAPI.updateWhatsAppConfig).not.toHaveBeenCalled()
  })

  it('shows the backend validation message for WhatsApp credentials', async () => {
    vi.mocked(platformAPI.getBusiness).mockResolvedValue(detailBusiness)
    vi.mocked(platformAPI.updateWhatsAppConfig).mockRejectedValue({
      response: {
        status: 422,
        data: {
          detail: [{ msg: 'Value error, El WABA ID debe contener solo números.' }],
        },
      },
    })
    renderBusinessDetail()

    fireEvent.change(await screen.findByLabelText('Phone Number ID'), {
      target: { value: '1180291398493188' },
    })
    fireEvent.change(screen.getByLabelText('WABA ID'), {
      target: { value: '2183193562429781' },
    })
    fireEvent.click(screen.getByRole('button', { name: /guardar credenciales/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /El WABA ID debe contener solo números/i
    )
  })

  it('reports provider acceptance after creating an invitation', async () => {
    vi.mocked(platformAPI.createInvitation).mockResolvedValue({
      id: 5, email: 'owner@example.test', status: 'pending', delivery_status: 'sent',
      expires_at: '2026-11-12T10:00:00Z', created_at: '2026-11-09T10:00:00Z',
    })
    render(<MemoryRouter><AdminInvitations /></MemoryRouter>)
    fireEvent.change(await screen.findByLabelText('Correo del dueño'), { target: { value: 'owner@example.test' } })
    fireEvent.click(screen.getByRole('button', { name: /enviar invitación/i }))
    expect(await screen.findByRole('status')).toHaveTextContent('Resend aceptó el envío')
    expect(platformAPI.createInvitation).toHaveBeenCalledWith('owner@example.test')
  })
})
