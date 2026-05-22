import axios from 'axios';

// Configure Axios defaults
const apiClient = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
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
  (error) => {
    return Promise.reject(error);
  }
);

// Intercept 401s to wipe stale tokens and force logout
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('godseye_jwt_token');
      localStorage.removeItem('godseye_user');
      // Redirect to login if not already there
      if (!window.location.pathname.endsWith('/login')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  login: async (email, password) => {
    const response = await apiClient.post('/auth/login', { email, password });
    if (response.data.access_token) {
      localStorage.setItem('godseye_jwt_token', response.data.access_token);
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
  }
};

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
      zone_coordinates: zoneCoords
    });
    return response.data;
  },
  delete: async (id) => {
    const response = await apiClient.delete(`/cameras/${id}`);
    return response.data;
  }
};

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
  }
};

export const chatAPI = {
  query: async (message) => {
    const response = await apiClient.post('/chat', { message });
    return response.data;
  }
};

export default apiClient;
