/**
 * NIYANTRA Central API Client
 * Provides resilient fetch wrappers with configurable timeout, standard JSON parsing,
 * and graceful fallback handling for Phase 2 backend integration.
 */

const API_BASE_URL =
  (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL) ||
  'http://localhost:8000/api';

const DEFAULT_TIMEOUT_MS = 6000;

class ApiError extends Error {
  constructor(message, status = 0, data = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function request(endpoint, options = {}) {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;
  const { timeout = DEFAULT_TIMEOUT_MS, headers = {}, ...customConfig } = options;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    signal: controller.signal,
    ...customConfig,
  };

  try {
    const response = await fetch(url, config);
    clearTimeout(timer);

    let data = null;
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    if (!response.ok) {
      const errorMessage =
        (data && (data.detail || data.message)) ||
        `HTTP Request failed with status ${response.status}`;
      throw new ApiError(errorMessage, response.status, data);
    }

    return data;
  } catch (error) {
    clearTimeout(timer);
    if (error.name === 'AbortError') {
      throw new ApiError('Request timed out while connecting to backend server', 408);
    }
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(error.message || 'Network error connecting to NIYANTRA API', 0);
  }
}

export const api = {
  get: (endpoint, options) => request(endpoint, { method: 'GET', ...options }),
  post: (endpoint, body, options) =>
    request(endpoint, { method: 'POST', body: JSON.stringify(body), ...options }),
  put: (endpoint, body, options) =>
    request(endpoint, { method: 'PUT', body: JSON.stringify(body), ...options }),
  patch: (endpoint, body, options) =>
    request(endpoint, {
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    }),
  delete: (endpoint, options) => request(endpoint, { method: 'DELETE', ...options }),

  /**
   * Health probe to verify backend availability
   */
  async checkHealth() {
    try {
      const data = await request('/health', { timeout: 3000 });
      return { online: true, data };
    } catch {
      return { online: false, data: null };
    }
  },
};

export { API_BASE_URL, ApiError };
