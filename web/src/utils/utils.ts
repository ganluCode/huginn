/**
 * Format a timestamp as a relative time string (e.g., "2 hours ago", "3 days ago").
 * Uses Intl.RelativeTimeFormat for i18n support.
 * @param date - The date to format, or null to return "Never"
 * @returns A formatted relative time string
 */
export function formatRelativeTime(date: Date | null): string {
  if (date === null) {
    return 'Never';
  }

  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  // Less than a minute
  if (diffInSeconds < 60) {
    return 'just now';
  }

  const diffInMinutes = Math.floor(diffInSeconds / 60);
  if (diffInMinutes < 60) {
    const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
    return rtf.format(-diffInMinutes, 'minute');
  }

  const diffInHours = Math.floor(diffInMinutes / 60);
  if (diffInHours < 24) {
    const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
    return rtf.format(-diffInHours, 'hour');
  }

  const diffInDays = Math.floor(diffInHours / 24);
  if (diffInDays < 30) {
    const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
    return rtf.format(-diffInDays, 'day');
  }

  const diffInMonths = Math.floor(diffInDays / 30);
  if (diffInMonths < 12) {
    const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
    return rtf.format(-diffInMonths, 'month');
  }

  const diffInYears = Math.floor(diffInDays / 365);
  const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  return rtf.format(-diffInYears, 'year');
}

/**
 * Check if a string is a valid URL.
 * @param str - The string to check
 * @returns true if the string is a valid URL, false otherwise
 */
export function isUrl(str: string): boolean {
  if (!str || str.length === 0) {
    return false;
  }

  try {
    const url = new URL(str);
    // Check that the protocol is http or https
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch {
    return false;
  }
}
