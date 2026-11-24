/**
 * NIYANTRA Central API Client
 * Provides resilient fetch wrappers with configurable timeout, standard JSON parsing,
 * and graceful fallback handling for Phase 2 backend integration.
 */

function resolveApiBaseUrl() {
  if (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  // When running in a browser, relative path '/api' works seamlessly on localhost, LAN IP, and public HTTPS
  if (typeof window !== 'undefined') {
    return '/api';
  }
  return 'http://localhost:8000/api';
}

const API_BASE_URL = resolveApiBaseUrl();

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

  const authHeaders = {};
  const storedApiKey =
    typeof window !== 'undefined' && window.localStorage
      ? window.localStorage.getItem('niyantra_api_key')
      : null;
  const apiKey =
    (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_KEY) ||
    storedApiKey;

  if (apiKey) {
    authHeaders['X-API-Key'] = apiKey;
  }

  const storedToken =
    typeof window !== 'undefined' && window.localStorage
      ? window.localStorage.getItem('niyantra_access_token')
      : null;
  if (storedToken) {
    authHeaders['Authorization'] = `Bearer ${storedToken}`;
  }

  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
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

export const authApi = {
  register: (name, email, password) =>
    api.post('/auth/register', { name, email, password }),
  login: (email, password) =>
    api.post('/auth/login', { email, password }),
  logout: () =>
    api.post('/auth/logout', {}),
  getMe: () =>
    api.get('/auth/me'),
};

export const devicesApi = {
  register: (deviceData) =>
    api.post('/devices/register', deviceData),
  list: (includeRevoked = true) =>
    api.get(`/devices?include_revoked=${includeRevoked}`),
  get: (deviceId) =>
    api.get(`/devices/${deviceId}`),
  update: (deviceId, data) =>
    api.patch(`/devices/${deviceId}`, data),
  revoke: (deviceId) =>
    api.post(`/devices/${deviceId}/revoke`, {}),
};

export { API_BASE_URL, ApiError };
