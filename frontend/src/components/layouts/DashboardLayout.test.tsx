import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DashboardLayout from './DashboardLayout'
import { useBusinessStore } from '@/store/businessStore'
import { businessAPI } from '@/services/api'

vi.mock('@/services/api', () => ({
  businessAPI: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  },
}))

const incompleteBusiness = {
  id: 41,
  owner: 8,
  name: '',
  category: 'barbershop',
  phone: '',
  timezone: 'America/Santo_Domingo',
  is_active: true,
  daily_notification_enabled: true,
  created_at: '2026-11-09T00:00:00Z',
  updated_at: '2026-11-09T00:00:00Z',
  onboarding_completed_at: null,
}

describe('DashboardLayout onboarding guard', () => {
  beforeEach(() => {
    localStorage.clear()
    useBusinessStore.setState({
      businesses: [],
      currentBusiness: null,
      isLoading: false,
      error: null,
    })
    vi.clearAllMocks()
  })

  it('keeps an incomplete business out of the panel and resumes onboarding', async () => {
    vi.mocked(businessAPI.list).mockResolvedValue([incompleteBusiness])
    vi.mocked(businessAPI.update).mockResolvedValue({
      ...incompleteBusiness,
      name: 'Barbería Norte',
      phone: '8095551111',
      onboarding_completed_at: '2026-11-09T12:00:00Z',
    })

    render(
      <MemoryRouter
        initialEntries={['/']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route path="/" element={<DashboardLayout />}>
            <Route index element={<div>Panel operativo</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByRole('heading', { name: 'Completa el perfil de tu negocio' })).toBeInTheDocument()
    expect(screen.queryByText('Panel operativo')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Nombre del negocio')).toHaveValue('')

    fireEvent.change(screen.getByLabelText('Nombre del negocio'), {
      target: { value: 'Barbería Norte' },
    })
    fireEvent.change(screen.getByLabelText('Teléfono del negocio'), {
      target: { value: '8095551111' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Completar alta' }))

    await waitFor(() =>
      expect(businessAPI.update).toHaveBeenCalledWith(
        41,
        expect.objectContaining({ name: 'Barbería Norte', phone: '8095551111' })
      )
    )
    expect(await screen.findByText('Panel operativo')).toBeInTheDocument()
  })
})
