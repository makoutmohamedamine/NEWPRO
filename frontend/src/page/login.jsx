import { useEffect, useRef, useState } from 'react';

export default function Login({ onLogin }) {
  const [isSignUp, setIsSignUp] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [welcomeName, setWelcomeName] = useState('');
  const welcomeTimer = useRef(null);

  // Login form state
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  // Sign Up form state
  const [signUpData, setSignUpData] = useState({
    username: '',
    email: '',
    first_name: '',
    last_name: '',
    password: '',
    password_confirm: '',
  });

  useEffect(() => {
    return () => {
      if (welcomeTimer.current) {
        clearTimeout(welcomeTimer.current);
      }
    };
  }, []);

  const triggerWelcomeAndLogin = (token, user) => {
    const userName =
      [user?.first_name, user?.last_name].filter(Boolean).join(' ').trim() ||
      user?.username ||
      'utilisateur';
    sessionStorage.setItem('welcome_user', userName);
    setWelcomeName(userName);
    welcomeTimer.current = setTimeout(() => {
      setWelcomeName('');
      onLogin(token, user);
    }, 1400);
  };

  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await fetch('http://127.0.0.1:8000/api/auth/login/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: loginUsername, password: loginPassword }),
      });
      const data = await res.json();
      if (res.ok) {
        localStorage.setItem('access_token', data.access);
        localStorage.setItem('refresh_token', data.refresh);
        localStorage.setItem('current_user', JSON.stringify(data.user));
        triggerWelcomeAndLogin(data.access, data.user);
      } else {
        setError(data.error || 'Identifiants incorrects');
      }
    } catch {
      setError('Erreur de connexion au serveur');
    }
    setLoading(false);
  };

  const handleSignUpSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // Validation client
    if (!signUpData.username || !signUpData.email || !signUpData.first_name || !signUpData.last_name) {
      setError('Tous les champs sont requis');
      return;
    }

    if (signUpData.password.length < 6) {
      setError('Le mot de passe doit faire au moins 6 caractères');
      return;
    }

    if (signUpData.password !== signUpData.password_confirm) {
      setError('Les mots de passe ne correspondent pas');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/auth/register/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: signUpData.username,
          email: signUpData.email,
          first_name: signUpData.first_name,
          last_name: signUpData.last_name,
          password: signUpData.password,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        localStorage.setItem('access_token', data.access);
        localStorage.setItem('refresh_token', data.refresh);
        localStorage.setItem('current_user', JSON.stringify(data.user));
        triggerWelcomeAndLogin(data.access, data.user);
      } else {
        setError(data.error || 'Erreur lors de la création du compte');
      }
    } catch {
      setError('Erreur de connexion au serveur');
    }
    setLoading(false);
  };

  const handleSignUpChange = (field, value) => {
    setSignUpData(prev => ({ ...prev, [field]: value }));
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      background: '#f9f9f9',
    }}>
      {welcomeName && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(13,13,13,0.75)',
          zIndex: 999,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <div style={{
            width: 'min(92vw, 560px)',
            borderRadius: 18,
            border: '1px solid rgba(255,255,255,0.14)',
            background: 'linear-gradient(135deg, #0d0d0d 0%, #1f2937 45%, #dc2626 120%)',
            color: '#fff',
            padding: '28px 30px',
            boxShadow: '0 22px 80px rgba(0,0,0,0.45)',
            animation: 'welcomePop 1.2s ease',
          }}>
            <div style={{
              width: 54, height: 54, borderRadius: '50%',
              border: '2px solid rgba(255,255,255,0.45)',
              display: 'grid', placeItems: 'center',
              fontSize: 24, marginBottom: 14,
              animation: 'welcomePulse 1s ease-in-out infinite',
            }}>
              👋
            </div>
            <div style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.12em', opacity: 0.76 }}>
              Connexion reussie
            </div>
            <div style={{ fontSize: '1.9rem', fontWeight: 800, lineHeight: 1.1, marginTop: 6 }}>
              Bienvenue {welcomeName}
            </div>
            <div style={{ marginTop: 8, color: 'rgba(255,255,255,0.82)' }}>
              Chargement de votre espace RH...
            </div>
          </div>
        </div>
      )}

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
        overflowY: 'auto',
        maxHeight: '100vh',
      }}>
        <div style={{ width: '100%', maxWidth: 380 }}>

          <div style={{ marginBottom: 36 }}>
            <h2 style={{
              fontSize: '1.6rem', fontWeight: 800,
              color: '#0d0d0d', marginBottom: 8,
            }}>
              {isSignUp ? 'Créer un compte' : 'Connexion'}
            </h2>
            <p style={{ color: '#6b7280', fontSize: '0.875rem' }}>
              {isSignUp 
                ? 'Inscrivez-vous pour accéder à la plateforme'
                : 'Entrez vos identifiants pour accéder à la plateforme'}
            </p>
          </div>

          {isSignUp ? (
            /* FORMULAIRE D'INSCRIPTION */
            <form onSubmit={handleSignUpSubmit}>

              <div style={{ marginBottom: 18 }}>
                <label style={{
                  display: 'block', marginBottom: 7,
                  fontSize: '0.8rem', fontWeight: 600,
                  color: '#374151', textTransform: 'uppercase', letterSpacing: 0.5,
                }}>
                  Prénom
                </label>
                <input
                  type="text"
                  value={signUpData.first_name}
                  onChange={e => handleSignUpChange('first_name', e.target.value)}
                  placeholder="Jean"
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

              <div style={{ marginBottom: 18 }}>
                <label style={{
                  display: 'block', marginBottom: 7,
                  fontSize: '0.8rem', fontWeight: 600,
                  color: '#374151', textTransform: 'uppercase', letterSpacing: 0.5,
                }}>
                  Nom
                </label>
                <input
                  type="text"
                  value={signUpData.last_name}
                  onChange={e => handleSignUpChange('last_name', e.target.value)}
                  placeholder="Dupont"
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

              <div style={{ marginBottom: 18 }}>
                <label style={{
                  display: 'block', marginBottom: 7,
                  fontSize: '0.8rem', fontWeight: 600,
                  color: '#374151', textTransform: 'uppercase', letterSpacing: 0.5,
                }}>
                  Email
                </label>
                <input
                  type="email"
                  value={signUpData.email}
                  onChange={e => handleSignUpChange('email', e.target.value)}
                  placeholder="votre@email.com"
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
                  value={signUpData.username}
                  onChange={e => handleSignUpChange('username', e.target.value)}
                  placeholder="jdupont"
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

              <div style={{ marginBottom: 18 }}>
                <label style={{
                  display: 'block', marginBottom: 7,
                  fontSize: '0.8rem', fontWeight: 600,
                  color: '#374151', textTransform: 'uppercase', letterSpacing: 0.5,
                }}>
                  Mot de passe
                </label>
                <input
                  type="password"
                  value={signUpData.password}
                  onChange={e => handleSignUpChange('password', e.target.value)}
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

              <div style={{ marginBottom: 24 }}>
                <label style={{
                  display: 'block', marginBottom: 7,
                  fontSize: '0.8rem', fontWeight: 600,
                  color: '#374151', textTransform: 'uppercase', letterSpacing: 0.5,
                }}>
                  Confirmer le mot de passe
                </label>
                <input
                  type="password"
                  value={signUpData.password_confirm}
                  onChange={e => handleSignUpChange('password_confirm', e.target.value)}
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
                    Création…
                  </>
                ) : 'S\'inscrire →'}
              </button>

              <p style={{
                textAlign: 'center', marginTop: 20,
                fontSize: '0.85rem', color: '#6b7280',
              }}>
                Vous avez déjà un compte ?{' '}
                <button
                  type="button"
                  onClick={() => { setIsSignUp(false); setError(''); }}
                  style={{
                    background: 'none', border: 'none',
                    color: '#dc2626', cursor: 'pointer',
                    fontWeight: 700, fontSize: 'inherit',
                    textDecoration: 'underline',
                  }}
                >
                  Se connecter
                </button>
              </p>
            </form>
          ) : (
            /* FORMULAIRE DE CONNEXION */
            <form onSubmit={handleLoginSubmit}>

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
                  value={loginUsername}
                  onChange={e => setLoginUsername(e.target.value)}
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
                  value={loginPassword}
                  onChange={e => setLoginPassword(e.target.value)}
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

              <p style={{
                textAlign: 'center', marginTop: 20,
                fontSize: '0.85rem', color: '#6b7280',
              }}>
                Pas encore inscrit ?{' '}
                <button
                  type="button"
                  onClick={() => { setIsSignUp(true); setError(''); }}
                  style={{
                    background: 'none', border: 'none',
                    color: '#dc2626', cursor: 'pointer',
                    fontWeight: 700, fontSize: 'inherit',
                    textDecoration: 'underline',
                  }}
                >
                  Créer un compte
                </button>
              </p>
            </form>
          )}

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
        @keyframes welcomePulse {
          0% { transform: scale(1); opacity: 0.85; }
          50% { transform: scale(1.1); opacity: 1; }
          100% { transform: scale(1); opacity: 0.85; }
        }
        @keyframes welcomePop {
          0% { transform: translateY(10px) scale(0.96); opacity: 0; }
          60% { transform: translateY(0) scale(1.01); opacity: 1; }
          100% { transform: translateY(0) scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

