import { useEffect, useRef, useState } from 'react';

function AuthField({ label, type = 'text', value, onChange, placeholder, autoComplete, required = true }) {
  return (
    <label className="auth-field">
      <span>{label}</span>
      <input
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required={required}
      />
    </label>
  );
}

function LoadingDot() {
  return <span className="auth-loading-dot" aria-hidden="true" />;
}

export default function LoginModern({ onLogin }) {
  const [isSignUp, setIsSignUp] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [welcomeName, setWelcomeName] = useState('');
  const welcomeTimer = useRef(null);

  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

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
      if (welcomeTimer.current) clearTimeout(welcomeTimer.current);
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
    }, 1200);
  };

  const handleLoginSubmit = async (event) => {
    event.preventDefault();
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
    } finally {
      setLoading(false);
    }
  };

  const handleSignUpSubmit = async (event) => {
    event.preventDefault();
    setError('');

    if (!signUpData.username || !signUpData.email || !signUpData.first_name || !signUpData.last_name) {
      setError('Tous les champs sont requis');
      return;
    }
    if (signUpData.password.length < 6) {
      setError('Le mot de passe doit faire au moins 6 caracteres');
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
        setError(data.error || 'Erreur lors de la creation du compte');
      }
    } catch {
      setError('Erreur de connexion au serveur');
    } finally {
      setLoading(false);
    }
  };

  const handleSignUpChange = (field, value) => {
    setSignUpData((previous) => ({ ...previous, [field]: value }));
  };

  return (
    <main className="auth-page">
      {welcomeName && (
        <div className="auth-welcome-overlay">
          <section className="auth-welcome-card">
            <div className="auth-welcome-mark">TM</div>
            <p>Connexion reussie</p>
            <h2>Bienvenue {welcomeName}</h2>
            <span>Preparation de votre espace recrutement...</span>
          </section>
        </div>
      )}

      <section className="auth-brand-panel" aria-label="Presentation TalentMatch IA">
        <div className="auth-brand-glow auth-brand-glow-one" />
        <div className="auth-brand-glow auth-brand-glow-two" />

        <div className="auth-logo-card">
          <img src="/logocld.png" alt="TalentMatch IA" />
        </div>

        <div className="auth-brand-content">
          <span className="auth-eyebrow">Plateforme RH intelligente</span>
          <h1>
            TalentMatch
            <strong> IA</strong>
          </h1>
          <p>
            Centralisez vos candidatures, analysez les profils et priorisez les meilleurs talents avec une experience claire,
            rapide et professionnelle.
          </p>
        </div>

        <div className="auth-feature-grid">
          <article>
            <span>01</span>
            <strong>Import automatique</strong>
            <p>Outlook, Gmail et CV centralises dans un seul espace.</p>
          </article>
          <article>
            <span>02</span>
            <strong>Matching IA</strong>
            <p>Scoring et ranking des candidats par poste.</p>
          </article>
          <article>
            <span>03</span>
            <strong>Pilotage RH</strong>
            <p>KPIs, pipeline et suivi des actions recruteur.</p>
          </article>
        </div>
      </section>

      <section className="auth-form-panel">
        <div className="auth-card">
          <div className="auth-card-topline" />
          <div className="auth-card-header">
            <span className="auth-card-kicker">{isSignUp ? 'Nouvel acces' : 'Acces securise'}</span>
            <h2>{isSignUp ? 'Creer un compte' : 'Connexion'}</h2>
            <p>
              {isSignUp
                ? 'Completez vos informations pour rejoindre la plateforme.'
                : 'Entrez vos identifiants pour acceder a votre espace TalentMatch IA.'}
            </p>
          </div>

          {isSignUp ? (
            <form className="auth-form" onSubmit={handleSignUpSubmit}>
              <div className="auth-two-cols">
                <AuthField
                  label="Prenom"
                  value={signUpData.first_name}
                  onChange={(e) => handleSignUpChange('first_name', e.target.value)}
                  placeholder="Amine"
                  autoComplete="given-name"
                />
                <AuthField
                  label="Nom"
                  value={signUpData.last_name}
                  onChange={(e) => handleSignUpChange('last_name', e.target.value)}
                  placeholder="Jabri"
                  autoComplete="family-name"
                />
              </div>

              <AuthField
                label="Email professionnel"
                type="email"
                value={signUpData.email}
                onChange={(e) => handleSignUpChange('email', e.target.value)}
                placeholder="nom@societe.com"
                autoComplete="email"
              />
              <AuthField
                label="Nom d'utilisateur"
                value={signUpData.username}
                onChange={(e) => handleSignUpChange('username', e.target.value)}
                placeholder="amine"
                autoComplete="username"
              />
              <AuthField
                label="Mot de passe"
                type="password"
                value={signUpData.password}
                onChange={(e) => handleSignUpChange('password', e.target.value)}
                placeholder="Minimum 6 caracteres"
                autoComplete="new-password"
              />
              <AuthField
                label="Confirmer le mot de passe"
                type="password"
                value={signUpData.password_confirm}
                onChange={(e) => handleSignUpChange('password_confirm', e.target.value)}
                placeholder="Repetez le mot de passe"
                autoComplete="new-password"
              />

              {error && <div className="auth-error">! {error}</div>}

              <button className="auth-submit" type="submit" disabled={loading}>
                {loading ? <><LoadingDot /> Creation...</> : 'Creer mon compte'}
              </button>

              <p className="auth-switch">
                Vous avez deja un compte ?
                <button type="button" onClick={() => { setIsSignUp(false); setError(''); }}>
                  Se connecter
                </button>
              </p>
            </form>
          ) : (
            <form className="auth-form" onSubmit={handleLoginSubmit}>
              <AuthField
                label="Nom d'utilisateur"
                value={loginUsername}
                onChange={(e) => setLoginUsername(e.target.value)}
                placeholder="Amine"
                autoComplete="username"
              />
              <AuthField
                label="Mot de passe"
                type="password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                placeholder="Votre mot de passe"
                autoComplete="current-password"
              />

              {error && <div className="auth-error">! {error}</div>}

              <button className="auth-submit" type="submit" disabled={loading}>
                {loading ? <><LoadingDot /> Connexion...</> : 'Se connecter'}
              </button>

              <p className="auth-switch">
                Pas encore inscrit ?
                <button type="button" onClick={() => { setIsSignUp(true); setError(''); }}>
                  Creer un compte
                </button>
              </p>
            </form>
          )}

          <div className="auth-footer">
            <span>TalentMatch IA</span>
            <span>Recruitment Intelligence Suite</span>
          </div>
        </div>
      </section>
    </main>
  );
}
