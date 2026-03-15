import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import HealthBadge from './HealthBadge'

// MSW server setup
const server = setupServer(
  // Default healthy response
  http.get('/api/health', () => {
    return HttpResponse.json({
      status: 'healthy',
      postgres: 'connected',
      redis: 'connected',
    })
  })
)

beforeAll(() => server.listen())
afterEach(() => {
  server.resetHandlers()
})
afterAll(() => server.close())

describe('HealthBadge', () => {
  describe('Initial mount', () => {
    it('requests GET /api/health immediately on mount', async () => {
      const handler = vi.fn(() =>
        HttpResponse.json({
          status: 'healthy',
          postgres: 'connected',
          redis: 'connected',
        })
      )
      server.use(http.get('/api/health', handler))

      render(<HealthBadge />)

      // Handler should be called immediately
      await waitFor(() => {
        expect(handler).toHaveBeenCalledTimes(1)
      })
    })
  })

  describe('Connected state (success)', () => {
    it('shows green dot and "Connected" text on successful health check (status 200)', async () => {
      server.use(
        http.get('/api/health', () => {
          return HttpResponse.json({
            status: 'healthy',
            postgres: 'connected',
            redis: 'connected',
          })
        })
      )

      render(<HealthBadge />)

      await waitFor(() => {
        const statusText = screen.getByText('Connected')
        expect(statusText).toBeInTheDocument()

        const statusDot = screen.getByTestId('health-status-dot')
        expect(statusDot).toHaveClass('bg-green-500')
      })
    })
  })

  describe('Disconnected state (failure)', () => {
    it('shows red dot and "Disconnected" text on non-2xx response', async () => {
      server.use(
        http.get('/api/health', () => {
          return HttpResponse.json(
            { detail: 'Service unavailable' },
            { status: 503 }
          )
        })
      )

      render(<HealthBadge />)

      await waitFor(() => {
        const statusText = screen.getByText('Disconnected')
        expect(statusText).toBeInTheDocument()

        const statusDot = screen.getByTestId('health-status-dot')
        expect(statusDot).toHaveClass('bg-red-500')
      })
    })

    it('shows red dot and "Disconnected" text on network error', async () => {
      server.use(
        http.get('/api/health', () => {
          // Simulate network error
          return HttpResponse.error()
        })
      )

      render(<HealthBadge />)

      await waitFor(() => {
        const statusText = screen.getByText('Disconnected')
        expect(statusText).toBeInTheDocument()

        const statusDot = screen.getByTestId('health-status-dot')
        expect(statusDot).toHaveClass('bg-red-500')
      })
    })
  })

  describe('Polling behavior', () => {
    it('sets up polling interval on mount', async () => {
      const setIntervalSpy = vi.spyOn(global, 'setInterval')
      server.use(
        http.get('/api/health', () => {
          return HttpResponse.json({
            status: 'healthy',
            postgres: 'connected',
            redis: 'connected',
          })
        })
      )

      render(<HealthBadge />)

      // Wait for initial render
      await waitFor(() => {
        expect(screen.getByTestId('health-status-dot')).toBeInTheDocument()
      })

      // setInterval should have been called with 30 seconds
      expect(setIntervalSpy).toHaveBeenCalledWith(
        expect.any(Function),
        30000
      )

      setIntervalSpy.mockRestore()
    })
  })

  describe('Cleanup', () => {
    it('clears interval on unmount (no memory leaks)', async () => {
      const clearIntervalSpy = vi.spyOn(global, 'clearInterval')
      server.use(
        http.get('/api/health', () => {
          return HttpResponse.json({
            status: 'healthy',
            postgres: 'connected',
            redis: 'connected',
          })
        })
      )

      const { unmount } = render(<HealthBadge />)

      // Wait for component to mount
      await waitFor(() => {
        expect(screen.getByTestId('health-status-dot')).toBeInTheDocument()
      })

      // Unmount component
      unmount()

      // clearInterval should have been called
      expect(clearIntervalSpy).toHaveBeenCalled()

      clearIntervalSpy.mockRestore()
    })
  })
})
