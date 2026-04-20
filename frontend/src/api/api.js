import axios from 'axios';

const API = axios.create({
    baseURL: 'http://127.0.0.1:8000/api',
});

// ── Injecteur automatique du token JWT ────────────────────────────────────────
API.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
});

// ── Rafraîchissement automatique du token expiré (401) ───────────────────────
let isRefreshing = false;
let pendingQueue = [];          // requêtes en attente du nouveau token

const processQueue = (error, token = null) => {
    pendingQueue.forEach(({ resolve, reject }) =>
        error ? reject(error) : resolve(token)
    );
    pendingQueue = [];
};

API.interceptors.response.use(
    (response) => response,
    async (error) => {
        const original = error.config;

        // Ignorer les erreurs non-401 et les retries déjà effectués
        if (error.response?.status !== 401 || original._retry) {
            return Promise.reject(error);
        }

        // Si le refresh lui-même échoue → déconnecter immédiatement
        if (original.url?.includes('/auth/refresh/') || original.url?.includes('/auth/login/')) {
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            localStorage.removeItem('current_user');
            window.location.reload();
            return Promise.reject(error);
        }

        original._retry = true;

        if (isRefreshing) {
            // Mettre la requête en file d'attente
            return new Promise((resolve, reject) => {
                pendingQueue.push({ resolve, reject });
            }).then(token => {
                original.headers.Authorization = `Bearer ${token}`;
                return API(original);
            });
        }

        isRefreshing = true;
        const refreshToken = localStorage.getItem('refresh_token');

        if (!refreshToken) {
            // Pas de refresh token → déconnecter
            localStorage.removeItem('access_token');
            localStorage.removeItem('current_user');
            isRefreshing = false;
            window.location.reload();
            return Promise.reject(error);
        }

        try {
            const res = await axios.post('http://127.0.0.1:8000/api/auth/refresh/', {
                refresh: refreshToken,
            });
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

// ── Candidats & Postes ────────────────────────────────────────────────────────
export const getCandidats    = ()     => API.get('/candidats/');
export const getCandidature  = ()     => API.get('/candidatures/');
export const getPostes       = ()     => API.get('/postes/');
export const createPoste     = (data) => API.post('/postes/', data);
export const updatePoste     = (id, data) => API.put(`/postes/${id}/`, data);
export const deletePoste     = (id)   => API.delete(`/postes/${id}/`);
export const createCandidat  = (data) => API.post('/candidats/', data);
export const getDashboard    = ()     => API.get('/dashboard/');

// ── Upload manuel ─────────────────────────────────────────────────────────────
export const uploadCV = (data) => API.post('/candidates/upload/', data, {
    headers: { 'Content-Type': 'multipart/form-data' },
});

// ── Pipeline Gmail ────────────────────────────────────────────────────────────
export const triggerGmailSync = () => API.post('/gmail/sync/');
export const getGmailStatus   = () => API.get('/gmail/status/');
export const getGmailDebug    = () => API.get('/gmail/debug/');

// ── Pipeline Outlook (legacy) ─────────────────────────────────────────────────
export const triggerOutlookSync  = ()  => API.post('/outlook/sync/');
export const getOutlookStatus    = ()  => API.get('/outlook/status/');

// ── Dossiers par domaine ──────────────────────────────────────────────────────
export const getDossiers = () => API.get('/dossiers/');

// ── Analyse ML ────────────────────────────────────────────────────────────────
export const analyseCV = (formData) => API.post('/ml/analyse/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
});

// ── Setup initial (premier administrateur) ────────────────────────────────────
export const checkSetup      = ()     => API.get('/auth/check-setup/');
export const setupSuperuser  = (data) => API.post('/auth/setup/', data);

// ── Gestion des utilisateurs (admin uniquement) ───────────────────────────────
export const getUsers        = ()         => API.get('/users/');
export const createUser      = (data)     => API.post('/users/create/', data);
export const updateUser      = (id, data) => API.patch(`/users/${id}/`, data);
export const deleteUser      = (id)       => API.delete(`/users/${id}/delete/`);
export const toggleUserActive = (id)     => API.patch(`/users/${id}/toggle/`);
export const getMe           = ()         => API.get('/auth/me/');

// ── Analyse IA (Claude) ───────────────────────────────────────────────────────
export const analyseCV_IA  = (formData) => API.post('/ai/analyse/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
});
export const scoreCV_IA    = (formData) => API.post('/ai/score/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
});
