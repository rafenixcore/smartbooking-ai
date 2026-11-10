import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import Login from './Login'

vi.mock('@/store/authStore', () => ({
  useAuthStore: () => ({ login: vi.fn(), isLoading: false, error: null }),
}))
vi.mock('@/store/businessStore', () => ({
  useBusinessStore: () => ({ fetchBusinesses: vi.fn() }),
}))

describe('Login', () => {
  it('offers existing owners sign-in without public registration or demo credentials', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Login />
      </MemoryRouter>
    )

    expect(screen.getByRole('button', { name: 'Entrar a mi cuenta' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /registr/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/cuenta de demostración/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/demo@rafenixcore\.com/i)).not.toBeInTheDocument()
  })
})
