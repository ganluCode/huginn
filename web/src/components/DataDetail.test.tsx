import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DataDetail } from './DataDetail';

describe('DataDetail', () => {
  describe('basic rendering', () => {
    it('should render key-value pairs from data object', () => {
      const data = {
        title: 'Test Title',
        score: 100,
        url: 'https://example.com',
      };

      render(<DataDetail data={data} />);

      expect(screen.getByText('title')).toBeInTheDocument();
      expect(screen.getByText('Test Title')).toBeInTheDocument();
      expect(screen.getByText('score')).toBeInTheDocument();
      expect(screen.getByText('100')).toBeInTheDocument();
    });

    it('should display keys in gray color', () => {
      const data = { field: 'value' };
      render(<DataDetail data={data} />);

      const keyElement = screen.getByText('field');
      expect(keyElement).toHaveClass('text-gray-500');
    });

    it('should display "No details available" when data is empty object', () => {
      render(<DataDetail data={{}} />);
      expect(screen.getByText('No details available')).toBeInTheDocument();
    });

    it('should display "No details available" when data is null', () => {
      render(<DataDetail data={null} />);
      expect(screen.getByText('No details available')).toBeInTheDocument();
    });
  });

  describe('URL handling', () => {
    it('should render URL values as clickable links', () => {
      const data = { url: 'https://example.com' };
      render(<DataDetail data={data} />);

      const link = screen.getByRole('link', { name: 'https://example.com' });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute('href', 'https://example.com');
      expect(link).toHaveAttribute('target', '_blank');
    });

    it('should render multiple URLs as links', () => {
      const data = {
        url: 'https://example.com',
        link: 'https://test.org',
      };
      render(<DataDetail data={data} />);

      expect(screen.getByRole('link', { name: 'https://example.com' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'https://test.org' })).toBeInTheDocument();
    });

    it('should not render non-URL strings as links', () => {
      const data = { text: 'plain text value' };
      render(<DataDetail data={data} />);

      expect(screen.queryByRole('link')).not.toBeInTheDocument();
      expect(screen.getByText('plain text value')).toBeInTheDocument();
    });
  });

  describe('nested objects and arrays', () => {
    it('should format objects as JSON string', () => {
      const data = {
        metadata: { author: 'John', date: '2026-01-01' },
      };
      render(<DataDetail data={data} />);

      const valueElement = screen.getByText(/"author"/);
      expect(valueElement).toBeInTheDocument();
      expect(valueElement).toHaveClass('font-mono', 'text-xs');
    });

    it('should format arrays as JSON string', () => {
      const data = {
        tags: ['react', 'typescript', 'testing'],
      };
      render(<DataDetail data={data} />);

      const valueElement = screen.getByText(/"react"/);
      expect(valueElement).toBeInTheDocument();
      expect(valueElement).toHaveClass('font-mono', 'text-xs');
    });
  });

  describe('value types', () => {
    it('should display numbers as-is', () => {
      const data = {
        count: 42,
        price: 19.99,
        zero: 0,
        negative: -100,
      };
      render(<DataDetail data={data} />);

      expect(screen.getByText('42')).toBeInTheDocument();
      expect(screen.getByText('19.99')).toBeInTheDocument();
      expect(screen.getByText('0')).toBeInTheDocument();
      expect(screen.getByText('-100')).toBeInTheDocument();
    });

    it('should display boolean values', () => {
      const data = {
        isActive: true,
        isDeleted: false,
      };
      render(<DataDetail data={data} />);

      expect(screen.getByText('true')).toBeInTheDocument();
      expect(screen.getByText('false')).toBeInTheDocument();
    });

    it('should display null and undefined values', () => {
      const data = {
        nullable: null,
        undefinable: undefined,
      };
      render(<DataDetail data={data} />);

      expect(screen.getByText('null')).toBeInTheDocument();
      expect(screen.getByText('undefined')).toBeInTheDocument();
    });
  });

  describe('complex nested structures', () => {
    it('should handle deeply nested objects', () => {
      const data = {
        nested: {
          level1: {
            level2: {
              value: 'deep',
            },
          },
        },
      };
      render(<DataDetail data={data} />);

      expect(screen.getByText(/"deep"/)).toBeInTheDocument();
    });

    it('should handle arrays with mixed types', () => {
      const data = {
        mixed: [1, 'two', { three: 3 }, [4, 5]],
      };
      render(<DataDetail data={data} />);

      expect(screen.getByText(/"two"/)).toBeInTheDocument();
    });
  });
});
