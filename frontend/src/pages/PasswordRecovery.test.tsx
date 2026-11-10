import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ForgotPassword from './ForgotPassword'
import ResetPassword from './ResetPassword'
import { authAPI } from '@/services/api'

vi.mock('@/services/api', () => ({
  authAPI: {
    requestPasswordReset: vi.fn(),
    confirmPasswordReset: vi.fn(),
  },
}))

describe('password recovery screens', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows the same confirmation after a neutral request response', async () => {
    vi.mocked(authAPI.requestPasswordReset).mockResolvedValue(undefined)
    render(<MemoryRouter><ForgotPassword /></MemoryRouter>)
    fireEvent.change(screen.getByLabelText('Correo electrónico'), { target: { value: 'owner@example.com' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enviar enlace' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Si existe una cuenta asociada')
    expect(authAPI.requestPasswordReset).toHaveBeenCalledWith('owner@example.com')
  })

  it('removes the token fragment and sends it only in the confirmation body', async () => {
    window.history.replaceState({}, '', '/reset-password#token=one-time-secret')
    vi.mocked(authAPI.confirmPasswordReset).mockResolvedValue(undefined)
    render(<MemoryRouter initialEntries={['/reset-password']}><Routes><Route path="/reset-password" element={<ResetPassword />} /></Routes></MemoryRouter>)
    expect(await screen.findByLabelText('Nueva contraseña')).toBeInTheDocument()
    expect(window.location.hash).toBe('')
    fireEvent.change(screen.getByLabelText('Nueva contraseña'), { target: { value: 'a-very-long-password' } })
    fireEvent.change(screen.getByLabelText('Confirmar contraseña'), { target: { value: 'a-very-long-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar contraseña' }))
    await waitFor(() => expect(authAPI.confirmPasswordReset).toHaveBeenCalledWith('one-time-secret', 'a-very-long-password'))
    expect(await screen.findByRole('status')).toHaveTextContent('Tu contraseña se actualizó')
  })

  it('offers a new request when the reset link has expired or was already used', async () => {
    window.history.replaceState({}, '', '/reset-password#token=expired-token')
    vi.mocked(authAPI.confirmPasswordReset).mockRejectedValue(new Error('expired'))
    render(<MemoryRouter initialEntries={['/reset-password']}><Routes><Route path="/reset-password" element={<ResetPassword />} /></Routes></MemoryRouter>)
    fireEvent.change(await screen.findByLabelText('Nueva contraseña'), { target: { value: 'a-very-long-password' } })
    fireEvent.change(screen.getByLabelText('Confirmar contraseña'), { target: { value: 'a-very-long-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Guardar contraseña' }))
    expect(await screen.findByText(/pudo haber vencido, ya se usó/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Solicitar otro enlace' })).toHaveAttribute('href', '/forgot-password')
  })
})
