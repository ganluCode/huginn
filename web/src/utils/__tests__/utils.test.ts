import { describe, it, expect } from 'vitest';
import { formatRelativeTime, isUrl } from '../utils';

describe('formatRelativeTime', () => {
  it('should return "just now" or similar for current time', () => {
    const now = new Date();
    const result = formatRelativeTime(now);
    expect(result).toMatch(/just now|now|today/);
  });

  it('should return relative time string containing "hour" for 2 hours ago', () => {
    const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000);
    const result = formatRelativeTime(twoHoursAgo);
    expect(result.toLowerCase()).toContain('hour');
  });

  it('should return "Never" for null input', () => {
    const result = formatRelativeTime(null);
    expect(result).toBe('Never');
  });

  it('should return relative time string containing "minute" for recent time', () => {
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
    const result = formatRelativeTime(fiveMinutesAgo);
    expect(result.toLowerCase()).toContain('minute');
  });

  it('should return relative time string containing "day" for days ago', () => {
    const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000);
    const result = formatRelativeTime(threeDaysAgo);
    expect(result.toLowerCase()).toContain('day');
  });
});

describe('isUrl', () => {
  it('should return true for https URL', () => {
    expect(isUrl('https://example.com')).toBe(true);
  });

  it('should return true for http URL', () => {
    expect(isUrl('http://example.com')).toBe(true);
  });

  it('should return true for URL with path and query', () => {
    expect(isUrl('https://example.com/path?query=value')).toBe(true);
  });

  it('should return false for plain text', () => {
    expect(isUrl('some plain text')).toBe(false);
  });

  it('should return false for email address', () => {
    expect(isUrl('user@example.com')).toBe(false);
  });

  it('should return false for URL without protocol', () => {
    expect(isUrl('example.com')).toBe(false);
  });

  it('should return false for empty string', () => {
    expect(isUrl('')).toBe(false);
  });
});
