import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SpiderStatusList from './SpiderStatusList'
import type { Spider } from '../types/api'

// Mock the apiClient
vi.mock('../api/client', () => ({
  apiClient: {
    post: vi.fn(),
  },
}))

import { apiClient } from '../api/client'

describe('SpiderStatusList', () => {
  const mockSpiders: Spider[] = [
    {
      name: 'hackernews',
      engine: 'scrapy',
      category: 'tech',
      schedule: '0 */6 * * *',
      enabled: true,
      last_run_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      last_status: 'success',
      item_count: 150,
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      name: 'github_trending',
      engine: 'scrapy',
      category: 'tech',
      schedule: '0 */12 * * *',
      enabled: true,
      last_run_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
      last_status: 'failed',
      item_count: 45,
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      name: 'crypto_price',
      engine: 'scrapy',
      category: 'finance',
      schedule: null,
      enabled: false,
      last_run_at: null,
      last_status: null,
      item_count: 0,
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      name: 'weibo_hot',
      engine: 'rpa',
      category: 'social',
      schedule: '*/30 * * * *',
      enabled: true,
      last_run_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      last_status: 'running',
      item_count: 200,
      created_at: '2024-01-01T00:00:00Z',
    },
  ]

  const mockOnRefresh = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  describe('Normal state - with spiders', () => {
    it('renders each spider as a row', () => {
      render(<SpiderStatusList spiders={mockSpiders} onRefresh={mockOnRefresh} />)

      expect(screen.getByText('hackernews')).toBeInTheDocument()
      expect(screen.getByText('github_trending')).toBeInTheDocument()
      expect(screen.getByText('crypto_price')).toBeInTheDocument()
      expect(screen.getByText('weibo_hot')).toBeInTheDocument()
    })

    it('displays category badge for each spider', () => {
      render(<SpiderStatusList spiders={mockSpiders} onRefresh={mockOnRefresh} />)

      // Use getAllByText since there are multiple tech spiders
      const techBadges = screen.getAllByText('tech')
      expect(techBadges.length).toBe(2)
      expect(screen.getByText('finance')).toBeInTheDocument()
      expect(screen.getByText('social')).toBeInTheDocument()
    })

    it('displays item_count for each spider', () => {
      render(<SpiderStatusList spiders={mockSpiders} onRefresh={mockOnRefresh} />)

      expect(screen.getByText('150')).toBeInTheDocument()
      expect(screen.getByText('45')).toBeInTheDocument()
      expect(screen.getByText('0')).toBeInTheDocument()
      expect(screen.getByText('200')).toBeInTheDocument()
    })

    it('shows green dot for success status', () => {
      render(<SpiderStatusList spiders={mockSpiders} onRefresh={mockOnRefresh} />)

      const successRow = screen.getByText('hackernews').closest('tr')
      expect(successRow?.querySelector('.bg-green-500')).toBeInTheDocument()
    })

    it('shows red dot for failed status', () => {
      render(<SpiderStatusList spiders={mockSpiders} onRefresh={mockOnRefresh} />)

      const failedRow = screen.getByText('github_trending').closest('tr')
      expect(failedRow?.querySelector('.bg-red-500')).toBeInTheDocument()
    })

    it('shows blue dot for running status', () => {
      render(<SpiderStatusList spiders={mockSpiders} onRefresh={mockOnRefresh} />)

      const runningRow = screen.getByText('weibo_hot').closest('tr')
      expect(runningRow?.querySelector('.bg-blue-500')).toBeInTheDocument()
    })

    it('shows gray dot for null/undefined status', () => {
      render(<SpiderStatusList spiders={mockSpiders} onRefresh={mockOnRefresh} />)

      const nullStatusRow = screen.getByText('crypto_price').closest('tr')
      expect(nullStatusRow?.querySelector('.bg-gray-400')).toBeInTheDocument()
    })

    it('displays relative time for last_run_at', () => {
      render(<SpiderStatusList spiders={mockSpiders} onRefresh={mockOnRefresh} />)

      // Should show time ago text
      const timeElements = screen.getAllByText(/ago|hour|minute/i)
      expect(timeElements.length).toBeGreaterThan(0)
    })

    it('displays "Never" when last_run_at is null', () => {
      render(<SpiderStatusList spiders={mockSpiders} onRefresh={mockOnRefresh} />)

      // crypto_price has null last_run_at
      const neverElements = screen.getAllByText('Never')
      expect(neverElements.length).toBeGreaterThan(0)
    })
  })

  describe('Trigger button interactions', () => {
    it('calls POST /api/spiders/{name}/run when trigger button is clicked', async () => {
      const user = userEvent.setup()
      vi.mocked(apiClient.post).mockResolvedValue({ message: 'Spider triggered' })

      render(<SpiderStatusList spiders={mockSpiders} onRefresh={mockOnRefresh} />)

      const triggerButton = screen.getAllByRole('button', { name: /trigger/i })[0]
      await user.click(triggerButton)

      expect(apiClient.post).toHaveBeenCalledWith('/spiders/hackernews/run')
    })

    it('shows "Triggered" message on successful API response', async () => {
      const user = userEvent.setup()
      vi.mocked(apiClient.post).mockResolvedValue({ message: 'Spider triggered' })

      render(<SpiderStatusList spiders={mockSpiders} onRefresh={mockOnRefresh} />)

      const triggerButton = screen.getAllByRole('button', { name: /trigger/i })[0]
      await user.click(triggerButton)

      expect(await screen.findByText('Triggered')).toBeInTheDocument()
    })

    it('shows "Already running" message on 409 response', async () => {
      const user = userEvent.setup()
      const conflictError: any = new Error('Conflict')
      conflictError.status = 409
      vi.mocked(apiClient.post).mockRejectedValue(conflictError)

      render(<SpiderStatusList spiders={mockSpiders} onRefresh={mockOnRefresh} />)

      const triggerButton = screen.getAllByRole('button', { name: /trigger/i })[0]
      await user.click(triggerButton)

      expect(await screen.findByText('Already running')).toBeInTheDocument()
    })

    it('shows "Error" message on API failure', async () => {
      const user = userEvent.setup()
      vi.mocked(apiClient.post).mockRejectedValue(new Error('Network error'))

      render(<SpiderStatusList spiders={mockSpiders} onRefresh={mockOnRefresh} />)

      const triggerButton = screen.getAllByRole('button', { name: /trigger/i })[0]
      await user.click(triggerButton)

      expect(await screen.findByText('Error')).toBeInTheDocument()
    })

    it('disables button during API request', async () => {
      const user = userEvent.setup()
      let resolvePromise: (value: any) => void
      vi.mocked(apiClient.post).mockReturnValue(
        new Promise(resolve => {
          resolvePromise = resolve
        })
      )

      render(<SpiderStatusList spiders={mockSpiders} onRefresh={mockOnRefresh} />)

      const triggerButton = screen.getAllByRole('button', { name: /trigger/i })[0]
      await user.click(triggerButton)

      // Button should be disabled during request
      expect(triggerButton).toBeDisabled()

      // Resolve the promise - button should be replaced with "Triggered" text
      resolvePromise!({ message: 'Spider triggered' })

      // The "Triggered" message should appear, replacing the button
      await waitFor(() => {
        expect(screen.getByText('Triggered')).toBeInTheDocument()
        // Original button reference is now stale since it was replaced
      })
    })

    it('prevents multiple clicks when request is in progress', async () => {
      const user = userEvent.setup()
      let resolvePromise: (value: any) => void
      vi.mocked(apiClient.post).mockReturnValue(
        new Promise(resolve => {
          resolvePromise = resolve
        })
      )

      render(<SpiderStatusList spiders={mockSpiders} onRefresh={mockOnRefresh} />)

      const triggerButton = screen.getAllByRole('button', { name: /trigger/i })[0]

      // First click
      await user.click(triggerButton)
      expect(apiClient.post).toHaveBeenCalledTimes(1)

      // Second click should be ignored (button disabled)
      await user.click(triggerButton)
      expect(apiClient.post).toHaveBeenCalledTimes(1)

      // Resolve the promise
      resolvePromise!({ message: 'Spider triggered' })
    })
  })

  describe('Loading state', () => {
    it('shows loading skeleton when loading=true', () => {
      render(<SpiderStatusList spiders={mockSpiders} loading={true} onRefresh={mockOnRefresh} />)

      const loadingElement = screen.getByTestId(/loading|skeleton/i)
      expect(loadingElement).toBeInTheDocument()
    })

    it('prioritizes loading state over spider list', () => {
      render(<SpiderStatusList spiders={mockSpiders} loading={true} onRefresh={mockOnRefresh} />)

      // Loading should be shown
      expect(screen.getByTestId(/loading|skeleton/i)).toBeInTheDocument()

      // Spider names should not be visible
      expect(screen.queryByText('hackernews')).not.toBeInTheDocument()
    })
  })

  describe('Empty state', () => {
    it('displays empty state message when spiders array is empty', () => {
      render(<SpiderStatusList spiders={[]} onRefresh={mockOnRefresh} />)

      expect(screen.getByText(/no spiders/i)).toBeInTheDocument()
    })
  })

  describe('Component structure', () => {
    it('uses only Tailwind utility classes, no inline styles', () => {
      const { container } = render(<SpiderStatusList spiders={mockSpiders} onRefresh={mockOnRefresh} />)

      const styledElements = container.querySelectorAll('[style]')
      expect(styledElements.length).toBe(0)
    })

    it('is accessible - buttons have proper labels', () => {
      render(<SpiderStatusList spiders={mockSpiders} onRefresh={mockOnRefresh} />)

      const buttons = screen.getAllByRole('button')
      buttons.forEach(button => {
        expect(button).toHaveAttribute('aria-label')
      })
    })
  })
})
