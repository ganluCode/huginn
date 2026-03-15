/**
 * API Client
 *
 * Provides a typed HTTP client for communicating with the Huginn backend API.
 * All requests are prefixed with `/api` and include proper error handling.
 */

const BASE_URL = '/api';

interface ApiError extends Error {
  status?: number;
}

/**
 * Parse response body as JSON
 */
async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const status = response.status;
    let detail = `HTTP ${status}`;

    try {
      const body = await response.json();
      if (typeof body === 'object' && body !== null && 'detail' in body) {
        detail = String(body.detail);
      }
    } catch {
      // If response is not JSON, use status text
      if (response.statusText) {
        detail = response.statusText;
      }
    }

    const error: ApiError = new Error(detail);
    error.status = status;
    throw error;
  }

  return response.json() as Promise<T>;
}

/**
 * Build URL with query parameters
 */
function buildUrl(path: string, params?: Record<string, string>): string {
  const url = new URL(path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      url.searchParams.set(key, value);
    });
  }
  return url.pathname + url.search;
}

/**
 * API client with typed methods
 */
export const apiClient = {
  /**
   * Make a GET request
   * @param path - API endpoint path (e.g., '/spiders')
   * @param params - Optional query parameters
   * @returns Parsed JSON response
   */
  get: async <T>(path: string, params?: Record<string, string>): Promise<T> => {
    const url = buildUrl(`${BASE_URL}${path}`, params);

    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
        },
      });
      return await parseResponse<T>(response);
    } catch (error) {
      // Network errors (connection refused, timeout, etc.)
      if (error instanceof TypeError && error.message === 'Failed to fetch') {
        throw new Error('Network error');
      }
      throw error;
    }
  },

  /**
   * Make a POST request
   * @param path - API endpoint path (e.g., '/spiders/run')
   * @param body - Request body to serialize as JSON
   * @returns Parsed JSON response
   */
  post: async <T>(path: string, body?: unknown): Promise<T> => {
    const url = `${BASE_URL}${path}`;

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: body ? JSON.stringify(body) : undefined,
      });
      return await parseResponse<T>(response);
    } catch (error) {
      // Network errors (connection refused, timeout, etc.)
      if (error instanceof TypeError && error.message === 'Failed to fetch') {
        throw new Error('Network error');
      }
      throw error;
    }
  },
};
