import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import RecentDataFeed from './RecentDataFeed'

describe('RecentDataFeed', () => {
  const mockItems = [
    {
      id: 1,
      source: 'hackernews',
      category: 'tech',
      collected_at: new Date(Date.now() - 2 * 60 * 60 * 1000), // 2 hours ago
      data: {
        title: 'Test Story 1',
        url: 'https://example.com/1',
      },
    },
    {
      id: 2,
      source: 'github',
      category: 'tech',
      collected_at: new Date(Date.now() - 24 * 60 * 60 * 1000), // 1 day ago
      data: {
        title: 'Test Repository',
        url: 'https://github.com/test/repo',
      },
    },
  ]

  describe('Normal state - with items', () => {
    it('renders each item as a row', () => {
      render(<RecentDataFeed items={mockItems} loading={false} />)

      // Should render both items
      expect(screen.getByText('Test Story 1')).toBeInTheDocument()
      expect(screen.getByText('Test Repository')).toBeInTheDocument()
    })

    it('displays title from data.data.title when it exists', () => {
      render(<RecentDataFeed items={mockItems} loading={false} />)

      expect(screen.getByText('Test Story 1')).toBeInTheDocument()
      expect(screen.getByText('Test Repository')).toBeInTheDocument()
    })

    it('falls back to {source} #{id} when title does not exist', () => {
      const itemsWithoutTitle = [
        {
          id: 123,
          source: 'weibo',
          category: 'social',
          collected_at: new Date(),
          data: {},
        },
      ]

      render(<RecentDataFeed items={itemsWithoutTitle} loading={false} />)

      expect(screen.getByText('weibo #123')).toBeInTheDocument()
    })

    it('displays source as a badge with background color', () => {
      render(<RecentDataFeed items={mockItems} loading={false} />)

      // Check for source badges
      const hackernewsBadge = screen.getByText('hackernews')
      expect(hackernewsBadge).toBeInTheDocument()

      const githubBadge = screen.getByText('github')
      expect(githubBadge).toBeInTheDocument()
    })

    it('displays relative time for collected_at', () => {
      render(<RecentDataFeed items={mockItems} loading={false} />)

      // Should show "2 hours ago" and "1 day ago" (in some format)
      const timeTexts = screen.getAllByText(/ago|day|hour/i)
      expect(timeTexts.length).toBeGreaterThan(0)
    })

    it('shows external link icon when data.data.url exists', () => {
      render(<RecentDataFeed items={mockItems} loading={false} />)

      // Check for external links - they should have target="_blank"
      const externalLinks = screen.getAllByRole('link').filter(link => {
        const htmlElement = link as HTMLAnchorElement
        return htmlElement.target === '_blank' && htmlElement.href.includes('http')
      })

      expect(externalLinks.length).toBeGreaterThan(0)
    })

    it('external link opens in new window with target="_blank"', () => {
      render(<RecentDataFeed items={mockItems} loading={false} />)

      const firstItemLink = screen.getByRole('link', { name: /Test Story 1/i })
      expect(firstItemLink).toHaveAttribute('target', '_blank')
    })

    it('does not show external link icon when url does not exist', () => {
      const itemsWithoutUrl = [
        {
          id: 1,
          source: 'internal',
          category: 'tech',
          collected_at: new Date(),
          data: {
            title: 'Internal Item',
          },
        },
      ]

      render(<RecentDataFeed items={itemsWithoutUrl} loading={false} />)

      expect(screen.getByText('Internal Item')).toBeInTheDocument()
      // No external link should be present
      const externalLinks = screen.queryAllByRole('link').filter(link => {
        const htmlElement = link as HTMLAnchorElement
        return htmlElement.target === '_blank'
      })
      expect(externalLinks.length).toBe(0)
    })
  })

  describe('Empty state', () => {
    it('displays empty state message when items is empty array', () => {
      render(<RecentDataFeed items={[]} loading={false} />)

      expect(screen.getByText(/no data/i)).toBeInTheDocument()
    })

    it('displays empty state message when items is null or undefined', () => {
      render(<RecentDataFeed items={null} loading={false} />)

      expect(screen.getByText(/no data/i)).toBeInTheDocument()
    })
  })

  describe('Loading state', () => {
    it('displays loading skeleton or spinner when loading=true', () => {
      render(<RecentDataFeed items={[]} loading={true} />)

      // Should show some loading indicator
      const loadingElement = screen.getByTestId(/loading|skeleton/i)
      expect(loadingElement).toBeInTheDocument()
    })

    it('prioritizes loading state over empty state', () => {
      render(<RecentDataFeed items={[]} loading={true} />)

      // Loading indicator should be present
      expect(screen.getByTestId(/loading|skeleton/i)).toBeInTheDocument()

      // Empty state message should not be visible
      const emptyMessage = screen.queryByText(/no data/i)
      expect(emptyMessage).not.toBeInTheDocument()
    })
  })

  describe('Component structure', () => {
    it('uses only Tailwind utility classes, no inline styles', () => {
      const { container } = render(<RecentDataFeed items={mockItems} loading={false} />)

      const styledElements = container.querySelectorAll('[style]')
      expect(styledElements.length).toBe(0)
    })

    it('is accessible - supports keyboard navigation for links', () => {
      render(<RecentDataFeed items={mockItems} loading={false} />)

      const links = screen.getAllByRole('link')
      links.forEach(link => {
        expect(link).toHaveAttribute('href')
      })
    })
  })
})
