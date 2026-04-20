import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Dashboard from './page/Dashboard';
import Dossiers from './page/Dossiers';
import Candidats from './page/Candidats';
import Postes from './page/Postes';
import OutlookSync from './components/OutlookSync';
import Login from './page/login';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('access_token'));

  const handleLogin = (accessToken) => {
    localStorage.setItem('access_token', accessToken);
    setToken(accessToken);
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setToken(null);
  };

  if (!token) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <BrowserRouter>
      <div className="app-shell">
        <Sidebar onLogout={handleLogout} />
        <main className="app-main">
          <Routes>
            <Route path="/"          element={<Dashboard />} />
            <Route path="/dossiers"  element={<Dossiers />} />
            <Route path="/candidats" element={<Candidats />} />
            <Route path="/postes"    element={<Postes />} />
            <Route path="/outlook"   element={<OutlookSync />} />
            <Route path="*"          element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
