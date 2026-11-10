import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AcceptInvitation from './AcceptInvitation'
import { authAPI } from '@/services/api'

vi.mock('@/services/api', () => ({
  authAPI: {
    getInvitation: vi.fn(),
    acceptInvitation: vi.fn(),
  },
}))

describe('AcceptInvitation', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows the invited email read-only and accepts only password fields', async () => {
    window.history.replaceState({}, '', '/invitation#token=secret-token')
    vi.mocked(authAPI.getInvitation).mockResolvedValue({
      email: 'owner@example.com',
      expires_at: '2026-11-12T12:00:00Z',
    })
    vi.mocked(authAPI.acceptInvitation).mockResolvedValue(undefined)

    render(
      <MemoryRouter
        initialEntries={['/invitation']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route path="/invitation" element={<AcceptInvitation />} />
          <Route path="/login" element={<div>Acceso</div>} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByText('owner@example.com')).toBeInTheDocument()
    expect(screen.queryByLabelText(/correo/i)).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Contraseña'), {
      target: { value: 'a-long-owner-password' },
    })
    fireEvent.change(screen.getByLabelText('Confirmar contraseña'), {
      target: { value: 'a-long-owner-password' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Aceptar invitación' }))

    await waitFor(() =>
      expect(authAPI.acceptInvitation).toHaveBeenCalledWith(
        'secret-token',
        'a-long-owner-password'
      )
    )
    expect(await screen.findByRole('link', { name: 'Iniciar sesión' })).toHaveAttribute('href', '/login')
  })

  it('shows a neutral invalid-link state when the preview is rejected', async () => {
    window.history.replaceState({}, '', '/invitation#token=invalid-token')
    vi.mocked(authAPI.getInvitation).mockRejectedValue(new Error('invalid'))

    render(
      <MemoryRouter initialEntries={['/invitation']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/invitation" element={<AcceptInvitation />} />
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByText(/no es válido o venció/i)).toBeInTheDocument()
    expect(screen.queryByLabelText('Contraseña')).not.toBeInTheDocument()
  })

  it('prevents a second acceptance request while the first is pending', async () => {
    window.history.replaceState({}, '', '/invitation#token=one-use-token')
    vi.mocked(authAPI.getInvitation).mockResolvedValue({
      email: 'owner@example.com',
      expires_at: '2026-11-12T12:00:00Z',
    })
    let resolveAcceptance!: () => void
    vi.mocked(authAPI.acceptInvitation).mockImplementation(
      () => new Promise((resolve) => { resolveAcceptance = resolve })
    )

    render(
      <MemoryRouter initialEntries={['/invitation']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/invitation" element={<AcceptInvitation />} />
        </Routes>
      </MemoryRouter>
    )
    fireEvent.change(await screen.findByLabelText('Contraseña'), {
      target: { value: 'a-long-owner-password' },
    })
    fireEvent.change(screen.getByLabelText('Confirmar contraseña'), {
      target: { value: 'a-long-owner-password' },
    })
    const submit = screen.getByRole('button', { name: 'Aceptar invitación' })
    fireEvent.click(submit)
    fireEvent.click(submit)

    expect(authAPI.acceptInvitation).toHaveBeenCalledTimes(1)
    resolveAcceptance()
    expect(await screen.findByText(/tu contraseña quedó configurada/i)).toBeInTheDocument()
  })
})
