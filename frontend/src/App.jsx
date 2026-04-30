import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Dashboard from './page/Dashboard';
import Dossiers from './page/Dossiers';
import DossiersCV from './page/DossiersCV';
import Candidats from './page/Candidats';
import Postes from './page/Postes';
import OutlookSync from './components/OutlookSync';

import AnalyseIA from './page/AnalyseIA';
import GestionUsers from './page/GestionUsers';
import Login from './page/login';
import Setup from './page/Setup';
import { checkSetup } from './api/api';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('access_token'));
  const [currentUser, setCurrentUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('current_user') || 'null'); }
    catch { return null; }
  });
  // null = en cours de vérification, true = setup requis, false = login normal
  const [needsSetup, setNeedsSetup] = useState(token ? false : null);
  const [welcomeToast, setWelcomeToast] = useState('');

  // Vérifier si un admin existe au chargement (seulement si pas connecté)
  useEffect(() => {
    if (!token) {
      // Timeout de sécurité : si le backend ne répond pas en 3s → afficher login
      const timeout = setTimeout(() => setNeedsSetup(false), 3000);
      checkSetup()
        .then(res => { clearTimeout(timeout); setNeedsSetup(res.data.needs_setup); })
        .catch(() => { clearTimeout(timeout); setNeedsSetup(false); });
      return () => clearTimeout(timeout);
    } else {
      setNeedsSetup(false);
    }
  }, [token]);

  // Toujours rafraîchir les données utilisateur depuis le serveur au chargement
  useEffect(() => {
    if (token) {
      import('./api/api').then(({ getMe }) => {
        getMe().then(res => {
          if (res.data && res.data.user) {
            setCurrentUser(res.data.user);
            localStorage.setItem('current_user', JSON.stringify(res.data.user));
          }
        }).catch(() => {
          handleLogout();
        });
      });
    }
  }, [token]);

  const handleLogin = (accessToken, user) => {
    localStorage.setItem('access_token', accessToken);
    if (user) localStorage.setItem('current_user', JSON.stringify(user));
    const displayName =
      [user?.first_name, user?.last_name].filter(Boolean).join(' ').trim()
      || user?.username
      || sessionStorage.getItem('welcome_user')
      || '';
    if (displayName) {
      setWelcomeToast(displayName);
      sessionStorage.removeItem('welcome_user');
      setTimeout(() => setWelcomeToast(''), 2200);
    }
    setToken(accessToken);
    setCurrentUser(user);
    setNeedsSetup(false);
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('current_user');
    setToken(null);
    setCurrentUser(null);
  };

  // Pas encore connecté
  if (!token) {
    // Vérification en cours
    if (needsSetup === null) {
      return (
        <div style={{
          minHeight: '100vh', display: 'flex',
          alignItems: 'center', justifyContent: 'center',
          background: '#f9f9f9', color: '#6b7280', fontSize: '0.9rem',
        }}>
          Chargement…
        </div>
      );
    }
    // Aucun admin → page de setup
    if (needsSetup) {
      return <Setup onSetupComplete={handleLogin} />;
    }
    // Admin existe → page de login
    return <Login onLogin={handleLogin} />;
  }

  const isAdmin = currentUser?.role === 'admin' || currentUser?.is_staff === true || currentUser?.is_superuser === true;

  return (
    <BrowserRouter>
      <div className="app-shell">
        {welcomeToast && (
          <div className="welcome-toast">
            <span className="welcome-toast-icon">👋</span>
            <span>Bienvenue {welcomeToast}</span>
          </div>
        )}
        <Sidebar onLogout={handleLogout} currentUser={currentUser} />
        <main className="app-main">
          <Routes>
            <Route path="/"          element={<Dashboard />} />
            <Route path="/dossiers"    element={<Dossiers />} />
            <Route path="/dossiers-cv" element={<DossiersCV />} />
            <Route path="/candidats" element={<Candidats />} />
            <Route path="/postes"    element={<Postes />} />
            <Route path="/outlook"    element={<OutlookSync />} />
            
            <Route path="/analyse-ia" element={<AnalyseIA />} />
            {/* Route réservée aux admins */}
            <Route path="/utilisateurs" element={isAdmin ? <GestionUsers /> : <Navigate to="/" />} />
            <Route path="*"          element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
