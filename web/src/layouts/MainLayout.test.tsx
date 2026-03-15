import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MainLayout from './MainLayout'

// Mock Outlet
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    Outlet: () => <div data-testid="outlet">Outlet Content</div>,
  }
})

describe('MainLayout', () => {
  // Reset window.innerWidth before each test
  const originalInnerWidth = window.innerWidth
  beforeEach(() => {
    window.innerWidth = originalInnerWidth
  })

  afterEach(() => {
    window.innerWidth = originalInnerWidth
  })

  describe('Desktop view (≥768px)', () => {
    beforeEach(() => {
      // Simulate desktop viewport
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 1024,
      })
      window.dispatchEvent(new Event('resize'))
    })

    it('renders sidebar with fixed 240px width', () => {
      render(<MainLayout />)
      const sidebar = screen.getByTestId('sidebar')
      expect(sidebar).toBeInTheDocument()
      expect(sidebar).toHaveClass('w-60') // w-60 = 240px in Tailwind
    })

    it('renders content area that takes remaining width', () => {
      render(<MainLayout />)
      const content = screen.getByTestId('content-area')
      expect(content).toBeInTheDocument()
      expect(content).toHaveClass('flex-1') // flex-1 = takes remaining space
    })

    it('hides hamburger menu button on desktop', () => {
      render(<MainLayout />)
      const hamburgerButton = screen.queryByTestId('hamburger-button')
      expect(hamburgerButton).not.toBeInTheDocument()
    })

    it('shows sidebar by default on desktop', () => {
      render(<MainLayout />)
      const sidebar = screen.getByTestId('sidebar')
      expect(sidebar).not.toHaveClass('-translate-x-full')
    })
  })

  describe('Mobile view (<768px)', () => {
    beforeEach(() => {
      // Simulate mobile viewport
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 375,
      })
      window.dispatchEvent(new Event('resize'))
    })

    it('shows hamburger menu button on mobile', () => {
      render(<MainLayout />)
      const hamburgerButton = screen.queryByTestId('hamburger-button')
      expect(hamburgerButton).toBeInTheDocument()
    })

    it('hides sidebar by default on mobile', () => {
      render(<MainLayout />)
      const sidebar = screen.getByTestId('sidebar')
      expect(sidebar).toHaveClass('-translate-x-full')
    })

    it('toggles sidebar visibility when hamburger button is clicked', async () => {
      const user = userEvent.setup()
      render(<MainLayout />)

      const sidebar = screen.getByTestId('sidebar')
      const hamburgerButton = screen.getByTestId('hamburger-button')

      // Sidebar should be hidden initially
      expect(sidebar).toHaveClass('-translate-x-full')

      // Click to show
      await user.click(hamburgerButton)
      expect(sidebar).not.toHaveClass('-translate-x-full')

      // Click to hide
      await user.click(hamburgerButton)
      expect(sidebar).toHaveClass('-translate-x-full')
    })
  })

  describe('Content area', () => {
    it('renders React Router Outlet in content area', () => {
      render(<MainLayout />)
      const outlet = screen.getByTestId('outlet')
      expect(outlet).toBeInTheDocument()
      expect(outlet).toHaveTextContent('Outlet Content')
    })
  })
})
