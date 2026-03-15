import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import StatCard from './StatCard'

describe('StatCard', () => {
  describe('Normal state', () => {
    it('displays title in gray small text and value in large bold text', () => {
      render(<StatCard title="Total Data" value="1,234" />)

      const title = screen.getByText('Total Data')
      expect(title).toBeInTheDocument()
      expect(title).toHaveClass('text-gray-500', 'text-sm')

      const value = screen.getByText('1,234')
      expect(value).toBeInTheDocument()
      expect(value).toHaveClass('text-2xl', 'font-bold')
    })

    it('accepts numeric value and displays it correctly', () => {
      render(<StatCard title="Count" value={42} />)

      const value = screen.getByText('42')
      expect(value).toBeInTheDocument()
    })

    it('accepts value of type string', () => {
      render(<StatCard title="Status" value="Active" />)

      const value = screen.getByText('Active')
      expect(value).toBeInTheDocument()
    })
  })

  describe('Loading state', () => {
    it('displays skeleton element with animate-pulse class when loading=true', () => {
      render(<StatCard title="Loading" value="—" loading={true} />)

      // Skeleton should be present in the value area
      const skeleton = screen.getByTestId('statcard-skeleton')
      expect(skeleton).toBeInTheDocument()
      expect(skeleton).toHaveClass('animate-pulse', 'bg-gray-200')
    })

    it('hides the actual value when loading=true', () => {
      render(<StatCard title="Loading" value="1,234" loading={true} />)

      // The value should not be visible when loading
      const value = screen.queryByText('1,234')
      expect(value).not.toBeInTheDocument()
    })
  })

  describe('Error state', () => {
    it('displays "—" (em dash) when error=true', () => {
      render(<StatCard title="Error" value="1,234" error={true} />)

      const emDash = screen.getByText('—')
      expect(emDash).toBeInTheDocument()
      expect(emDash).toHaveClass('text-2xl', 'font-bold')
    })

    it('hides the actual value when error=true', () => {
      render(<StatCard title="Error" value="1,234" error={true} />)

      // The value should not be visible when error
      const value = screen.queryByText('1,234')
      expect(value).not.toBeInTheDocument()
    })
  })

  describe('Loading and error together', () => {
    it('shows skeleton when both loading=true and error=true (loading takes precedence)', () => {
      render(<StatCard title="Both" value="1,234" loading={true} error={true} />)

      // Loading should take precedence over error
      const skeleton = screen.getByTestId('statcard-skeleton')
      expect(skeleton).toBeInTheDocument()

      const emDash = screen.queryByText('—')
      expect(emDash).not.toBeInTheDocument()
    })
  })

  describe('Component structure', () => {
    it('uses only Tailwind utility classes, no inline styles', () => {
      const { container } = render(<StatCard title="Test" value="100" />)

      // Check for absence of style attribute
      const styledElements = container.querySelectorAll('[style]')
      expect(styledElements.length).toBe(0)
    })
  })
})
