import { useState } from 'react';

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError]       = useState('');
  const [loading, setLoading]   = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch('http://127.0.0.1:8000/api/auth/login/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (res.ok) {
        localStorage.setItem('access_token', data.access);
        localStorage.setItem('refresh_token', data.refresh);
        localStorage.setItem('current_user', JSON.stringify(data.user));
        onLogin(data.access, data.user);
      } else {
        setError('Identifiants incorrects');
      }
    } catch {
      setError('Erreur de connexion au serveur');
    }
    setLoading(false);
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      background: '#f9f9f9',
    }}>
      {/* Panneau gauche — branding */}
      <div style={{
        width: '45%',
        background: '#0d0d0d',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'flex-start',
        padding: '60px 64px',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* Accent décoratif */}
        <div style={{
          position: 'absolute', top: 0, left: 0,
          width: '100%', height: 4,
          background: '#dc2626',
        }} />
        <div style={{
          position: 'absolute', bottom: -120, right: -120,
          width: 400, height: 400, borderRadius: '50%',
          background: 'rgba(220,38,38,0.06)',
        }} />

        {/* Logo */}
        <div style={{ marginBottom: 40 }}>
          <img
            src="/logocld.png"
            alt="Logo"
            style={{ height: 56, width: 'auto', objectFit: 'contain', display: 'block' }}
          />
        </div>

        <h1 style={{
          color: '#ffffff',
          fontSize: '2.4rem',
          fontWeight: 800,
          lineHeight: 1.15,
          marginBottom: 20,
          letterSpacing: -0.5,
        }}>
          COLORADO<br />
          RH<br />
          <span style={{ color: '#dc2626' }}>PLATEFORME</span>
        </h1>

        <p style={{
          color: '#9ca3af',
          fontSize: '0.9rem',
          lineHeight: 1.7,
          maxWidth: 300,
          marginBottom: 48,
        }}>
          Centralisez, classifiez et priorisez automatiquement
          les candidatures reçues via Outlook grâce au ML.
        </p>

        {/* Features */}
        {[
          'Import automatique via Outlook O365',
          'Classification ML par profil métier',
          'Scoring et ranking des candidats',
        ].map(f => (
          <div key={f} style={{
            display: 'flex', alignItems: 'center', gap: 12,
            marginBottom: 14,
          }}>
            <span style={{
              width: 20, height: 20, borderRadius: '50%',
              background: 'rgba(220,38,38,0.2)',
              border: '1.5px solid #dc2626',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 10, color: '#dc2626', flexShrink: 0,
            }}>✓</span>
            <span style={{ color: '#d1d5db', fontSize: '0.85rem' }}>{f}</span>
          </div>
        ))}
      </div>

      {/* Panneau droit — formulaire */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        padding: '60px 48px',
      }}>
        <div style={{ width: '100%', maxWidth: 380 }}>

          <div style={{ marginBottom: 36 }}>
            <h2 style={{
              fontSize: '1.6rem', fontWeight: 800,
              color: '#0d0d0d', marginBottom: 8,
            }}>
              Connexion
            </h2>
            <p style={{ color: '#6b7280', fontSize: '0.875rem' }}>
              Entrez vos identifiants pour accéder à la plateforme
            </p>
          </div>

          <form onSubmit={handleSubmit}>

            <div style={{ marginBottom: 18 }}>
              <label style={{
                display: 'block', marginBottom: 7,
                fontSize: '0.8rem', fontWeight: 600,
                color: '#374151', textTransform: 'uppercase', letterSpacing: 0.5,
              }}>
                Nom d'utilisateur
              </label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="admin"
                required
                style={{
                  width: '100%', padding: '12px 14px',
                  borderRadius: 8, fontSize: '0.925rem',
                  border: '1.5px solid #e5e7eb',
                  background: '#fff', outline: 'none',
                  boxSizing: 'border-box',
                  transition: 'border-color 0.2s',
                }}
                onFocus={e => e.target.style.borderColor = '#dc2626'}
                onBlur={e => e.target.style.borderColor = '#e5e7eb'}
              />
            </div>

            <div style={{ marginBottom: 24 }}>
              <label style={{
                display: 'block', marginBottom: 7,
                fontSize: '0.8rem', fontWeight: 600,
                color: '#374151', textTransform: 'uppercase', letterSpacing: 0.5,
              }}>
                Mot de passe
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                style={{
                  width: '100%', padding: '12px 14px',
                  borderRadius: 8, fontSize: '0.925rem',
                  border: '1.5px solid #e5e7eb',
                  background: '#fff', outline: 'none',
                  boxSizing: 'border-box',
                  transition: 'border-color 0.2s',
                }}
                onFocus={e => e.target.style.borderColor = '#dc2626'}
                onBlur={e => e.target.style.borderColor = '#e5e7eb'}
              />
            </div>

            {error && (
              <div style={{
                background: '#fef2f2', border: '1px solid #fecaca',
                color: '#dc2626', padding: '10px 14px',
                borderRadius: 8, marginBottom: 20,
                fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: 8,
              }}>
                <span>⚠</span> {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%', padding: '13px',
                borderRadius: 8, border: 'none',
                background: loading ? '#9ca3af' : '#dc2626',
                color: '#fff', fontSize: '0.95rem',
                fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
                transition: 'background 0.2s',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              }}
              onMouseEnter={e => { if (!loading) e.target.style.background = '#b91c1c'; }}
              onMouseLeave={e => { if (!loading) e.target.style.background = '#dc2626'; }}
            >
              {loading ? (
                <>
                  <span style={{
                    width: 16, height: 16, border: '2px solid rgba(255,255,255,0.4)',
                    borderTopColor: '#fff', borderRadius: '50%',
                    display: 'inline-block', animation: 'spin 0.7s linear infinite',
                  }} />
                  Connexion…
                </>
              ) : 'Se connecter →'}
            </button>
          </form>

          <p style={{
            textAlign: 'center', marginTop: 32,
            fontSize: '0.78rem', color: '#9ca3af',
          }}>
            CV Manager — Recruitment Intelligence Suite
          </p>
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
