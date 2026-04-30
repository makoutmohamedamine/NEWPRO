import axios from 'axios';

const API = axios.create({
  baseURL: 'http://127.0.0.1:8000/api',
});

API.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let isRefreshing = false;
let pendingQueue = [];

const processQueue = (error, token = null) => {
  pendingQueue.forEach(({ resolve, reject }) => (error ? reject(error) : resolve(token)));
  pendingQueue = [];
};

API.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status !== 401 || original?._retry) {
      return Promise.reject(error);
    }
    if (original.url?.includes('/auth/refresh/') || original.url?.includes('/auth/login/')) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('current_user');
      window.location.reload();
      return Promise.reject(error);
    }

    original._retry = true;
    if (isRefreshing) {
      return new Promise((resolve, reject) => pendingQueue.push({ resolve, reject })).then((token) => {
        original.headers.Authorization = `Bearer ${token}`;
        return API(original);
      });
    }

    isRefreshing = true;
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('current_user');
      window.location.reload();
      return Promise.reject(error);
    }

    try {
      const res = await axios.post('http://127.0.0.1:8000/api/auth/refresh/', { refresh: refreshToken });
      const newToken = res.data.access;
      localStorage.setItem('access_token', newToken);
      API.defaults.headers.common.Authorization = `Bearer ${newToken}`;
      processQueue(null, newToken);
      original.headers.Authorization = `Bearer ${newToken}`;
      return API(original);
    } catch (refreshError) {
      processQueue(refreshError, null);
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('current_user');
      window.location.reload();
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);

export const getDashboard = () => API.get('/dashboard/');
export const getCandidats = () => API.get('/candidates/');
export const updateCandidate = (id, data) => API.patch(`/candidates/${id}/update/`, data);
export const deleteCandidate = (id) => API.delete(`/candidates/${id}/delete/`);
export const getCandidateHistory = (id) => API.get(`/candidates/${id}/history/`);
export const getWorkflowStatuses = () => API.get('/workflow/statuses/');
export const getDomains = () => API.get('/domains/');
export const getDomainCandidates = (id) => API.get(`/domains/${id}/candidates/`);

export const getPostes = () => API.get('/postes/');
export const createPoste = (data) => API.post('/postes/', data);
export const updatePoste = (id, data) => API.put(`/postes/${id}/`, data);
export const deletePoste = (id) => API.delete(`/postes/${id}/`);

export const uploadCV = (data) =>
  API.post('/candidates/upload/', data, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

export const getDossiers = () => API.get('/dossiers/');
export const triggerOutlookSync = () => API.post('/outlook/sync/');
export const getOutlookStatus = () => API.get('/outlook/status/');
export const triggerGmailSync = () => API.post('/gmail/sync/');
export const getGmailStatus = () => API.get('/gmail/status/');
export const getGmailDebug = () => API.get('/gmail/debug/');

export const analyseCV = (formData) =>
  API.post('/ml/analyse/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

export const analyseCV_IA = (formData) =>
  API.post('/ai/analyse/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

export const scoreCV_IA = (formData) =>
  API.post('/ai/score/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

export const checkSetup = () => API.get('/auth/check-setup/');
export const setupSuperuser = (data) => API.post('/auth/setup/', data);
export const getMe = () => API.get('/auth/me/');

export const getUsers = () => API.get('/users/');
export const createUser = (data) => API.post('/users/create/', data);
export const updateUser = (id, data) => API.patch(`/users/${id}/`, data);
export const deleteUser = (id) => API.delete(`/users/${id}/delete/`);
export const toggleUserActive = (id) => API.patch(`/users/${id}/toggle/`);

export default API;
