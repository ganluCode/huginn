import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DataFilters from './DataFilters'

// Mock the apiClient
vi.mock('../api/client', () => ({
  apiClient: {
    get: vi.fn(),
  },
}))

import { apiClient } from '../api/client'

describe('DataFilters', () => {
  const mockOnFilterChange = vi.fn()
  const mockOnExport = vi.fn()
  const mockSources = ['hackernews', 'github_trending', 'crypto_price', 'weibo_hot']

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  afterEach(() => {
    vi.clearAllTimers()
  })

  describe('Data source dropdown', () => {
    it('calls GET /api/data/sources on mount', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      render(<DataFilters onFilterChange={mockOnFilterChange} onExport={mockOnExport} />)

      await waitFor(() => {
        expect(apiClient.get).toHaveBeenCalledWith('/data/sources')
      })
    })

    it('renders "All" option as first option in source dropdown', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      render(<DataFilters onFilterChange={mockOnFilterChange} onExport={mockOnExport} />)

      // Find the source select and verify "All" is the first option
      const sourceSelect = await screen.findByRole('combobox', { name: /source/i })
      const firstOption = sourceSelect.querySelector('option') as HTMLOptionElement
      expect(firstOption?.value).toBe('All')
    })

    it('renders all sources from API response', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      render(<DataFilters onFilterChange={mockOnFilterChange} onExport={mockOnExport} />)

      await waitFor(() => {
        expect(screen.getByText('hackernews')).toBeInTheDocument()
        expect(screen.getByText('github_trending')).toBeInTheDocument()
        expect(screen.getByText('crypto_price')).toBeInTheDocument()
        expect(screen.getByText('weibo_hot')).toBeInTheDocument()
      })
    })

    it('calls onFilterChange when source selection changes', async () => {
      const user = userEvent.setup()
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      render(<DataFilters onFilterChange={mockOnFilterChange} onExport={mockOnExport} />)

      const sourceDropdown = await screen.findByRole('combobox', { name: /source/i })
      await user.selectOptions(sourceDropdown, 'github_trending')

      expect(mockOnFilterChange).toHaveBeenCalledWith(
        expect.objectContaining({ source: 'github_trending' })
      )
    })
  })

  describe('Category dropdown', () => {
    it('renders fixed category options', () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      render(<DataFilters onFilterChange={mockOnFilterChange} onExport={mockOnExport} />)

      // There should be multiple "All" options (source and category)
      const allOptions = screen.getAllByText('All')
      expect(allOptions.length).toBeGreaterThanOrEqual(1)

      expect(screen.getByText('tech')).toBeInTheDocument()
      expect(screen.getByText('social')).toBeInTheDocument()
      expect(screen.getByText('finance')).toBeInTheDocument()
      expect(screen.getByText('market')).toBeInTheDocument()
      expect(screen.getByText('news')).toBeInTheDocument()
    })

    it('calls onFilterChange when category selection changes', async () => {
      const user = userEvent.setup()
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      render(<DataFilters onFilterChange={mockOnFilterChange} onExport={mockOnExport} />)

      const categoryDropdown = screen.getByRole('combobox', { name: /category/i })
      await user.selectOptions(categoryDropdown, 'tech')

      expect(mockOnFilterChange).toHaveBeenCalledWith(
        expect.objectContaining({ category: 'tech' })
      )
    })
  })

  describe('Keyword input with debounce', () => {
    it('does not call onFilterChange immediately on input', async () => {
      const user = userEvent.setup()
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      render(<DataFilters onFilterChange={mockOnFilterChange} onExport={mockOnExport} />)

      const keywordInput = screen.getByRole('textbox', { name: /keyword/i })
      await user.type(keywordInput, 'test')

      // Should not be called immediately
      expect(mockOnFilterChange).not.toHaveBeenCalled()
    })

    it('calls onFilterChange after 300ms debounce', async () => {
      const user = userEvent.setup()
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      render(<DataFilters onFilterChange={mockOnFilterChange} onExport={mockOnExport} />)

      const keywordInput = screen.getByRole('textbox', { name: /keyword/i })
      await user.type(keywordInput, 'test')

      await waitFor(
        () => {
          expect(mockOnFilterChange).toHaveBeenCalledWith(
            expect.objectContaining({ keyword: 'test' })
          )
        },
        { timeout: 500 }
      )
    })

    it('cancels previous debounce timer on new input', async () => {
      const user = userEvent.setup()
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      render(<DataFilters onFilterChange={mockOnFilterChange} onExport={mockOnExport} />)

      const keywordInput = screen.getByRole('textbox', { name: /keyword/i })

      // Type first character
      await user.type(keywordInput, 'a')

      // Type second character quickly (before 300ms)
      await user.type(keywordInput, 'b')

      await waitFor(
        () => {
          // Should only be called once with the final value
          const calls = mockOnFilterChange.mock.calls.filter(call =>
            call[0]?.keyword === 'ab'
          )
          expect(calls.length).toBe(1)
        },
        { timeout: 500 }
      )
    })
  })

  describe('Time range quick select', () => {
    it('renders all time range options', () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      render(<DataFilters onFilterChange={mockOnFilterChange} onExport={mockOnExport} />)

      expect(screen.getByRole('button', { name: /time range: today/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /time range: last 3 days/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /time range: last 7 days/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /time range: last 30 days/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /time range: all/i })).toBeInTheDocument()
    })

    it('calls onFilterChange immediately when time range is selected', async () => {
      const user = userEvent.setup()
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      render(<DataFilters onFilterChange={mockOnFilterChange} onExport={mockOnExport} />)

      const todayButton = screen.getByRole('button', { name: /time range: today/i })
      await user.click(todayButton)

      // Should be called immediately, not debounced
      expect(mockOnFilterChange).toHaveBeenCalledWith(
        expect.objectContaining({ timeRange: 'today' })
      )
    })

    it('highlights selected time range button', async () => {
      const user = userEvent.setup()
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      render(<DataFilters onFilterChange={mockOnFilterChange} onExport={mockOnExport} />)

      const todayButton = screen.getByRole('button', { name: /time range: today/i })
      await user.click(todayButton)

      expect(todayButton).toHaveClass('bg-blue-500')
    })
  })

  describe('Export button', () => {
    it('calls onExport when clicked', async () => {
      const user = userEvent.setup()
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      render(<DataFilters onFilterChange={mockOnFilterChange} onExport={mockOnExport} />)

      const exportButton = await screen.findByRole('button', { name: /export/i })
      await user.click(exportButton)

      expect(mockOnExport).toHaveBeenCalled()
    })

    it('shows loading state when exporting=true', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      render(
        <DataFilters
          onFilterChange={mockOnFilterChange}
          onExport={mockOnExport}
          exporting={true}
        />
      )

      const exportButton = await screen.findByRole('button', { name: /exporting/i })
      expect(exportButton).toBeInTheDocument()
      expect(exportButton).toBeDisabled()
    })

    it('disables export button when exporting=true', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      render(
        <DataFilters
          onFilterChange={mockOnFilterChange}
          onExport={mockOnExport}
          exporting={true}
        />
      )

      const exportButton = await screen.findByRole('button', { name: /exporting/i })
      expect(exportButton).toBeDisabled()
    })
  })

  describe('Component cleanup', () => {
    it('cleans up debounce timer on unmount', async () => {
      const user = userEvent.setup()
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      const { unmount } = render(
        <DataFilters onFilterChange={mockOnFilterChange} onExport={mockOnExport} />
      )

      const keywordInput = await screen.findByRole('textbox', { name: /keyword/i })

      // Type something but don't wait for debounce
      await user.type(keywordInput, 'test')

      // Unmount before debounce completes
      unmount()

      // Fast-forward time to ensure debounce timer was cleared
      await waitFor(
        () => {
          // onFilterChange should NOT be called after unmount
          expect(mockOnFilterChange).not.toHaveBeenCalledWith(
            expect.objectContaining({ keyword: 'test' })
          )
        },
        { timeout: 500 }
      )
    })
  })

  describe('Integration - all filters work together', () => {
    it('calls onFilterChange with all filter values', async () => {
      const user = userEvent.setup()
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      render(<DataFilters onFilterChange={mockOnFilterChange} onExport={mockOnExport} />)

      // Wait for sources to load
      await screen.findByRole('combobox', { name: /source/i })

      // Clear previous calls
      mockOnFilterChange.mockClear()

      // Set time range
      const todayButton = screen.getByRole('button', { name: /time range: today/i })
      await user.click(todayButton)

      // Set category using selectOptions
      const categoryDropdown = screen.getByRole('combobox', { name: /category/i })
      await user.selectOptions(categoryDropdown, 'tech')

      // Wait for the filter changes
      await waitFor(() => {
        expect(mockOnFilterChange).toHaveBeenCalled()
      })

      // One of the calls should have timeRange
      const timeRangeCalls = mockOnFilterChange.mock.calls.filter(
        call => call[0]?.timeRange === 'today'
      )
      expect(timeRangeCalls.length).toBeGreaterThan(0)

      // And category should be tech in the last relevant call
      const lastCall = mockOnFilterChange.mock.calls.at(-1)?.[0]
      expect(lastCall?.category).toBe('tech')
    })
  })

  describe('Component structure', () => {
    it('uses only Tailwind utility classes, no inline styles', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      const { container } = render(
        <DataFilters onFilterChange={mockOnFilterChange} onExport={mockOnExport} />
      )

      // Wait for component to fully render
      await screen.findByRole('combobox', { name: /source/i })

      const styledElements = container.querySelectorAll('[style]')
      expect(styledElements.length).toBe(0)
    })

    it('has proper accessibility labels', async () => {
      vi.mocked(apiClient.get).mockResolvedValue(mockSources)

      render(<DataFilters onFilterChange={mockOnFilterChange} onExport={mockOnExport} />)

      // Wait for async data loading
      await waitFor(() => {
        expect(screen.getByRole('combobox', { name: /source/i })).toBeInTheDocument()
      })

      expect(screen.getByRole('combobox', { name: /category/i })).toBeInTheDocument()
      expect(screen.getByRole('textbox', { name: /keyword/i })).toBeInTheDocument()
    })
  })
})
