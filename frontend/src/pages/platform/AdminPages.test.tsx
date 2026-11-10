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

describe('platform administration screens', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authState.value = { admin: null, ready: true, initialize: vi.fn(), logout: vi.fn() }
    vi.mocked(platformAPI.listBusinesses).mockResolvedValue(emptyBusinesses)
    vi.mocked(platformAPI.listInvitations).mockResolvedValue(emptyInvitations)
    vi.mocked(platformAPI.listAudit).mockResolvedValue({ items: [], total: 0, offset: 0, limit: 6 })
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
