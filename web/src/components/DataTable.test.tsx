import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DataTable } from './DataTable';
import type { CollectedData } from '../types/api';

const mockItem: CollectedData = {
  id: 1,
  source: 'hackernews',
  category: 'tech',
  collected_at: '2026-03-15T10:30:00Z',
  data: {
    title: 'Test Article Title',
    url: 'https://example.com/article',
    score: 100,
  },
};

const mockItems: CollectedData[] = [
  mockItem,
  {
    id: 2,
    source: 'github_trending',
    category: 'tech',
    collected_at: '2026-03-15T09:15:00Z',
    data: {
      title: 'Another Repo',
      stars: 500,
    },
  },
];

describe('DataTable', () => {
  describe('basic rendering', () => {
    it('should render table with 5 columns', () => {
      render(
        <DataTable
          items={mockItems}
          total={2}
          offset={0}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      // Check that table headers are rendered
      expect(screen.getByRole('columnheader', { name: /source/i })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: /title/i })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: /category/i })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: /time/i })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: /actions/i })).toBeInTheDocument();
    });

    it('should render data rows with source badge', () => {
      render(
        <DataTable
          items={mockItems}
          total={2}
          offset={0}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      expect(screen.getByText('hackernews')).toBeInTheDocument();
      expect(screen.getByText('github_trending')).toBeInTheDocument();
    });

    it('should render data rows with category badge', () => {
      render(
        <DataTable
          items={mockItems}
          total={2}
          offset={0}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      expect(screen.getAllByText('tech')).toHaveLength(2);
    });

    it('should render title from data.title field', () => {
      render(
        <DataTable
          items={mockItems}
          total={2}
          offset={0}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      expect(screen.getByText('Test Article Title')).toBeInTheDocument();
    });

    it('should display collected_at in YYYY-MM-DD HH:mm format', () => {
      render(
        <DataTable
          items={[mockItem]}
          total={1}
          offset={0}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      // 2026-03-15T10:30:00Z should be formatted based on local timezone
      // The format should include date and time
      const timeCell = screen.getByText(/2026-03-15/);
      expect(timeCell).toBeInTheDocument();
      // Check that time is formatted (not checking exact value due to timezone differences)
      expect(timeCell.textContent).toMatch(/\d{2}:\d{2}/);
    });

    it('should render expand button for each row', () => {
      render(
        <DataTable
          items={mockItems}
          total={2}
          offset={0}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      const expandButtons = screen.getAllByRole('button', { name: /Expand details for row/i });
      expect(expandButtons).toHaveLength(2);
    });
  });

  describe('title truncation', () => {
    it('should truncate title longer than 80 characters with ellipsis', () => {
      const longTitleItem: CollectedData = {
        ...mockItem,
        data: {
          ...mockItem.data,
          title: 'This is a very long title that exceeds eighty characters and should be truncated with an ellipsis at the end to indicate more content',
        },
      };

      render(
        <DataTable
          items={[longTitleItem]}
          total={1}
          offset={0}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      const titleElement = screen.getByText(/This is a very long title/);
      expect(titleElement).toHaveClass('truncate');
    });

    it('should not truncate short titles', () => {
      render(
        <DataTable
          items={mockItems}
          total={2}
          offset={0}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      const titleElement = screen.getByText('Test Article Title');
      expect(titleElement).toBeInTheDocument();
      expect(titleElement).toHaveTextContent('Test Article Title');
    });
  });

  describe('expand/collapse functionality', () => {
    it('should show DataDetail component when expand button is clicked', async () => {
      const user = userEvent.setup();
      render(
        <DataTable
          items={[mockItem]}
          total={1}
          offset={0}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      const expandButton = screen.getByRole('button', { name: /Expand details for row 1/i });
      await user.click(expandButton);

      // DataDetail should be visible with data fields
      expect(screen.getByText('title')).toBeInTheDocument();
      // Check for unique DataDetail field (not in table row)
      expect(screen.getByText('100')).toBeInTheDocument(); // score value
    });

    it('should hide DataDetail component when expand button is clicked again', async () => {
      const user = userEvent.setup();
      render(
        <DataTable
          items={[mockItem]}
          total={1}
          offset={0}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      const expandButton = screen.getByRole('button', { name: /Expand details for row 1/i });

      // First click to expand
      await user.click(expandButton);
      expect(screen.getByText('title')).toBeInTheDocument();

      // Second click to collapse
      await user.click(expandButton);
      expect(screen.queryByText('title')).not.toBeInTheDocument();
    });

    it('should only allow one row to be expanded at a time', async () => {
      const user = userEvent.setup();
      render(
        <DataTable
          items={mockItems}
          total={2}
          offset={0}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      const expandButtons = screen.getAllByRole('button', { name: /Expand details for row/i });

      // Expand first row
      await user.click(expandButtons[0]);
      expect(screen.getByText('title')).toBeInTheDocument(); // First row's detail

      // Expand second row - first row should collapse
      await user.click(expandButtons[1]);
      // The title key is only shown in DataDetail, so if first row is collapsed,
      // there should be only one "title" text (from second row's detail)
      expect(screen.getAllByText('title')).toHaveLength(1);
      // Second row's detail should be visible (unique field)
      expect(screen.getByText('500')).toBeInTheDocument(); // stars value from second item
    });
  });

  describe('pagination', () => {
    it('should display pagination controls with current page and total', () => {
      render(
        <DataTable
          items={mockItems}
          total={25}
          offset={0}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      expect(screen.getAllByRole('button', { name: 'Previous' }).length).toBeGreaterThan(0);
      expect(screen.getAllByRole('button', { name: 'Next' }).length).toBeGreaterThan(0);
      // Check for pagination info - "total results" text is unique to pagination
      expect(screen.getByText(/total results/)).toBeInTheDocument();
      expect(screen.getByText('25')).toBeInTheDocument(); // total count
    });

    it('should disable previous button on first page', () => {
      render(
        <DataTable
          items={mockItems}
          total={25}
          offset={0}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      const prevButtons = screen.getAllByRole('button', { name: 'Previous' });
      prevButtons.forEach(btn => {
        expect(btn).toBeDisabled();
      });
    });

    it('should disable next button on last page', () => {
      render(
        <DataTable
          items={mockItems}
          total={25}
          offset={20}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      // Any button with name Next should be disabled on last page
      const nextButtons = screen.getAllByRole('button', { name: 'Next' });
      nextButtons.forEach(btn => {
        expect(btn).toBeDisabled();
      });
    });

    it('should enable both buttons when not on first or last page', () => {
      render(
        <DataTable
          items={mockItems}
          total={30}
          offset={10}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      const prevButtons = screen.getAllByRole('button', { name: 'Previous' });
      const nextButtons = screen.getAllByRole('button', { name: 'Next' });

      prevButtons.forEach(btn => {
        expect(btn).not.toBeDisabled();
      });
      nextButtons.forEach(btn => {
        expect(btn).not.toBeDisabled();
      });
    });

    it('should call onPageChange with previous offset when previous button is clicked', async () => {
      const user = userEvent.setup();
      const onPageChange = vi.fn();

      render(
        <DataTable
          items={mockItems}
          total={30}
          offset={10}
          limit={10}
          loading={false}
          onPageChange={onPageChange}
        />
      );

      const prevButtons = screen.getAllByRole('button', { name: 'Previous' });
      await user.click(prevButtons[0]);

      expect(onPageChange).toHaveBeenCalledWith(0); // 10 - 10 = 0
    });

    it('should call onPageChange with next offset when next button is clicked', async () => {
      const user = userEvent.setup();
      const onPageChange = vi.fn();

      render(
        <DataTable
          items={mockItems}
          total={30}
          offset={10}
          limit={10}
          loading={false}
          onPageChange={onPageChange}
        />
      );

      const nextButtons = screen.getAllByRole('button', { name: 'Next' });
      await user.click(nextButtons[0]);

      expect(onPageChange).toHaveBeenCalledWith(20); // 10 + 10 = 20
    });

    it('should display correct page number', () => {
      const { rerender } = render(
        <DataTable
          items={mockItems}
          total={30}
          offset={0}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      // Page 1 should be shown
      expect(screen.getByText('1')).toBeInTheDocument();

      rerender(
        <DataTable
          items={mockItems}
          total={30}
          offset={10}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      // After rerender, page 2 should be shown
      expect(screen.getByText('2')).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('should display "No data found" when items is empty and loading is false', () => {
      render(
        <DataTable
          items={[]}
          total={0}
          offset={0}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      expect(screen.getByText('No data found')).toBeInTheDocument();
    });

    it('should not display empty state when loading is true', () => {
      render(
        <DataTable
          items={[]}
          total={0}
          offset={0}
          limit={10}
          loading={true}
          onPageChange={vi.fn()}
        />
      );

      expect(screen.queryByText('No data found')).not.toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('should display skeleton rows when loading is true', () => {
      render(
        <DataTable
          items={[]}
          total={0}
          offset={0}
          limit={10}
          loading={true}
          onPageChange={vi.fn()}
        />
      );

      // Check for skeleton elements with animate-pulse class
      const skeletons = document.querySelectorAll('[data-testid="datatable-skeleton-row"]');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('should display skeleton rows when loading is true with existing items', () => {
      render(
        <DataTable
          items={mockItems}
          total={2}
          offset={0}
          limit={10}
          loading={true}
          onPageChange={vi.fn()}
        />
      );

      // When loading with items, should show skeletons
      const skeletons = document.querySelectorAll('[data-testid="datatable-skeleton-row"]');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  describe('accessibility', () => {
    it('should have aria-label on expand buttons', () => {
      render(
        <DataTable
          items={[mockItem]}
          total={1}
          offset={0}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      const expandButton = screen.getByRole('button', { name: /Expand details for row 1/i });
      expect(expandButton).toBeInTheDocument();
    });

    it('should update aria-expanded when row is expanded', async () => {
      const user = userEvent.setup();
      render(
        <DataTable
          items={[mockItem]}
          total={1}
          offset={0}
          limit={10}
          loading={false}
          onPageChange={vi.fn()}
        />
      );

      const expandButton = screen.getByRole('button', { name: /Expand details for row 1/i });
      expect(expandButton).toHaveAttribute('aria-expanded', 'false');

      await user.click(expandButton);
      expect(expandButton).toHaveAttribute('aria-expanded', 'true');
    });
  });
});
