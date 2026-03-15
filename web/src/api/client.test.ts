import { describe, it, expect, beforeAll, afterEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { apiClient } from './client';

// MSW server to mock fetch requests
const server = setupServer(
  // Mock successful GET request
  http.get('/api/test', () => {
    return HttpResponse.json({ message: 'success' });
  }),

  // Mock successful GET with query params
  http.get('/api/search', ({ request }) => {
    const url = new URL(request.url);
    const query = url.searchParams.get('q');
    return HttpResponse.json({ results: [`result for: ${query}`] });
  }),

  // Mock successful POST request
  http.post('/api/data', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({ created: true, ...body });
  }),

  // Mock 404 error
  http.get('/api/notfound', () => {
    return HttpResponse.json({ detail: 'Not found' }, { status: 404 });
  }),

  // Mock 500 error
  http.get('/api/error', () => {
    return HttpResponse.json({ detail: 'Internal error' }, { status: 500 });
  }),

  // Mock network error (connection refused)
  http.get('/api/network', () => {
    return HttpResponse.error();
  }),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());

describe('API Client', () => {
  describe('get<T>(path)', () => {
    it('should make GET request and return parsed JSON', async () => {
      const response = await apiClient.get<{ message: string }>('/test');
      expect(response).toEqual({ message: 'success' });
    });
  });

  describe('get<T>(path, params)', () => {
    it('should serialize params as query string and append to URL', async () => {
      const response = await apiClient.get<{ results: string[] }>('/search', {
        q: 'test query',
      });
      expect(response.results).toEqual(['result for: test query']);
    });

    it('should handle multiple query params', async () => {
      // Add a new handler for multiple params
      server.use(
        http.get('/api/multi', ({ request }) => {
          const url = new URL(request.url);
          const q = url.searchParams.get('q');
          const limit = url.searchParams.get('limit');
          return HttpResponse.json({ query: q, limit: Number(limit) });
        })
      );

      const response = await apiClient.get<{ query: string; limit: number }>(
        '/multi',
        { q: 'search', limit: '10' }
      );
      expect(response.query).toBe('search');
      expect(response.limit).toBe(10);
    });
  });

  describe('post<T>(path, body)', () => {
    it('should send POST request with JSON body', async () => {
      const requestBody = { name: 'test', value: 123 };
      const response = await apiClient.post<{
        created: boolean;
        name: string;
        value: number;
      }>('/data', requestBody);

      expect(response.created).toBe(true);
      expect(response.name).toBe('test');
      expect(response.value).toBe(123);
    });

    it('should set Content-Type to application/json', async () => {
      let receivedContentType = '';

      server.use(
        http.post('/api/check-content', async ({ request }) => {
          receivedContentType = request.headers.get('content-type') || '';
          return HttpResponse.json({ ok: true });
        })
      );

      await apiClient.post('/check-content', { data: 'test' });
      expect(receivedContentType).toBe('application/json');
    });
  });

  describe('error handling', () => {
    it('should throw Error with status and detail on non-2xx response', async () => {
      await expect(apiClient.get('/notfound')).rejects.toThrow('Not found');
      try {
        await apiClient.get('/notfound');
      } catch (e) {
        expect(e).toBeInstanceOf(Error);
        const error = e as Error & { status: number };
        expect(error.status).toBe(404);
        expect(error.message).toContain('Not found');
      }
    });

    it('should throw Error with status 500 and detail on server error', async () => {
      try {
        await apiClient.get('/error');
      } catch (e) {
        expect(e).toBeInstanceOf(Error);
        const error = e as Error & { status: number };
        expect(error.status).toBe(500);
        expect(error.message).toContain('Internal error');
      }
    });

    it('should throw Error with "Network error" on network failure', async () => {
      await expect(apiClient.get('/network')).rejects.toThrow('Network error');
      try {
        await apiClient.get('/network');
      } catch (e) {
        expect(e).toBeInstanceOf(Error);
        expect((e as Error).message).toBe('Network error');
      }
    });
  });
});
