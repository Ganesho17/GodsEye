import axios from 'axios';

/**
 * frontend/src/services/api.js
 * God's Eye — Unified API Service Layer
 *
 * Extended with:
 *  - devicesAPI : camera device CRUD
 *  - crowdAPI   : crowd history and surge status
 *
 * All existing exports (authAPI, camerasAPI, alertsAPI, chatAPI) are preserved unchanged.
 */

// ---- Axios client setup ----
const apiClient = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// Automatically inject JWT tokens into headers if logged in
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('godseye_jwt_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Intercept 401s to wipe stale tokens and force re-login
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('godseye_jwt_token');
      localStorage.removeItem('godseye_user');
      if (!window.location.pathname.endsWith('/login')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// ============================================================
// AUTH
// ============================================================
export const authAPI = {
  login: async (email, password) => {
    const response = await apiClient.post('/auth/login', { email, password });
    if (response.data.access_token) {
      localStorage.setItem('godseye_jwt_token', response.data.access_token);
    }
    if (response.data.user) {
      localStorage.setItem('godseye_user', JSON.stringify(response.data.user));
    }
    return response.data;
  },
  signup: async (name, email, password, role = 'operator') => {
    const response = await apiClient.post('/auth/signup', { name, email, password, role });
    return response.data;
  },
  me: async () => {
    const response = await apiClient.get('/auth/me');
    localStorage.setItem('godseye_user', JSON.stringify(response.data));
    return response.data;
  },
  logout: () => {
    localStorage.removeItem('godseye_jwt_token');
    localStorage.removeItem('godseye_user');
  },
};

// ============================================================
// CAMERAS (existing — unchanged)
// ============================================================
export const camerasAPI = {
  list: async () => {
    const response = await apiClient.get('/cameras');
    return response.data;
  },
  create: async (data) => {
    const response = await apiClient.post('/cameras', data);
    return response.data;
  },
  update: async (id, data) => {
    const response = await apiClient.put(`/cameras/${id}`, data);
    return response.data;
  },
  updateZone: async (id, zoneCoords) => {
    const response = await apiClient.post(`/cameras/${id}/zone`, {
      zone_coordinates: zoneCoords,
    });
    return response.data;
  },
  delete: async (id) => {
    const response = await apiClient.delete(`/cameras/${id}`);
    return response.data;
  },
  stats: async (id) => {
    const response = await apiClient.get(`/cameras/${id}/stats`);
    return response.data;
  },
};

// ============================================================
// ALERTS (existing — extended)
// ============================================================
export const alertsAPI = {
  list: async (filters = {}) => {
    const response = await apiClient.get('/alerts', { params: filters });
    return response.data;
  },
  stats: async () => {
    const response = await apiClient.get('/alerts/stats');
    return response.data;
  },
  resolve: async (id) => {
    const response = await apiClient.put(`/alerts/${id}/resolve`);
    return response.data;
  },
  resolveAll: async () => {
    const response = await apiClient.post('/alerts/resolve-all');
    return response.data;
  },
};

// ============================================================
// CHAT / AI ASSISTANT (existing — unchanged)
// ============================================================
export const chatAPI = {
  query: async (message) => {
    const response = await apiClient.post('/chat', { message });
    return response.data;
  },
};

// ============================================================
// DEVICES — NEW
// Multi-camera device management
// ============================================================
export const devicesAPI = {
  /** List all registered camera devices */
  list: async () => {
    const response = await apiClient.get('/cameras');
    return response.data;
  },

  /** Register a new camera device */
  create: async ({ name, type, source, location }) => {
    const response = await apiClient.post('/cameras', { name, type, source, location });
    return response.data;
  },

  /** Update camera settings (zone, thresholds, etc.) */
  update: async (id, data) => {
    const response = await apiClient.put(`/cameras/${id}`, data);
    return response.data;
  },

  /** Remove a camera device */
  delete: async (id) => {
    const response = await apiClient.delete(`/cameras/${id}`);
    return response.data;
  },

  /** Get per-camera telemetry stats */
  stats: async (id) => {
    const response = await apiClient.get(`/cameras/${id}/stats`);
    return response.data;
  },

  /** Update restricted zone for a camera */
  updateZone: async (id, zoneCoords) => {
    const response = await apiClient.post(`/cameras/${id}/zone`, { zone_coordinates: zoneCoords });
    return response.data;
  },
};

// ============================================================
// CROWD ANALYTICS — NEW
// ============================================================
export const crowdAPI = {
  /**
   * Returns time-series crowd count history.
   * @param {Object} params - { camera_id?, hours?, limit? }
   */
  history: async (params = {}) => {
    const response = await apiClient.get('/crowd/history', { params });
    return response.data;
  },

  /**
   * Returns current crowd surge status for all active cameras.
   */
  surgeStatus: async () => {
    const response = await apiClient.get('/crowd/surge');
    return response.data;
  },
};

export default apiClient;
