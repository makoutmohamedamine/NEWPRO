import { useState } from 'react';
import { setupSuperuser } from '../api/api';

export default function Setup({ onSetupComplete }) {
  const [form, setForm] = useState({
    username: '',
    email: '',
    first_name: '',
    last_name: '',
    password: '',
    confirm: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!form.username.trim()) return setError('Le nom d\'utilisateur est requis.');
    if (!form.email.trim()) return setError('L\'email est requis.');
    if (form.password.length < 6) return setError('Le mot de passe doit faire au moins 6 caractères.');
    if (form.password !== form.confirm) return setError('Les mots de passe ne correspondent pas.');

    setLoading(true);
    try {
      const { data } = await setupSuperuser({
        username: form.username.trim(),
        email: form.email.trim(),
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        password: form.password,
      });
      localStorage.setItem('access_token', data.access);
      localStorage.setItem('refresh_token', data.refresh);
      localStorage.setItem('current_user', JSON.stringify(data.user));
      onSetupComplete(data.access, data.user);
    } catch (err) {
      setError(err.response?.data?.error || 'Erreur lors de la création du compte.');
    }
    setLoading(false);
  };

  const inputStyle = {
    width: '100%',
    padding: '11px 13px',
    borderRadius: 8,
    border: '1.5px solid #e5e7eb',
    fontSize: '0.9rem',
    boxSizing: 'border-box',
    outline: 'none',
    background: '#fff',
  };

  const labelStyle = {
    display: 'block',
    fontSize: '0.78rem',
    fontWeight: 700,
    color: '#374151',
    marginBottom: 6,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', background: '#f9f9f9' }}>

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
        <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: 4, background: '#dc2626' }} />
        <div style={{ position: 'absolute', bottom: -120, right: -120, width: 400, height: 400, borderRadius: '50%', background: 'rgba(220,38,38,0.06)' }} />

        <div style={{ marginBottom: 40 }}>
          <img src="/logocld.png" alt="Logo" style={{ height: 56, width: 'auto', objectFit: 'contain', display: 'block' }} />
        </div>

        <h1 style={{ color: '#fff', fontSize: '2.4rem', fontWeight: 800, lineHeight: 1.15, marginBottom: 20, letterSpacing: -0.5 }}>
          COLORADO<br />RH<br />
          <span style={{ color: '#dc2626' }}>PLATEFORME</span>
        </h1>

        <p style={{ color: '#9ca3af', fontSize: '0.9rem', lineHeight: 1.7, maxWidth: 300, marginBottom: 40 }}>
          Bienvenue ! Créez le compte <strong style={{ color: '#fff' }}>administrateur principal</strong> pour initialiser la plateforme.
        </p>

        {[
          'Accès complet à la gestion des utilisateurs',
          'Création des comptes recruteurs RH',
          'Contrôle total de la plateforme',
        ].map(f => (
          <div key={f} style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
            <span style={{
              width: 20, height: 20, borderRadius: '50%',
              background: 'rgba(220,38,38,0.2)', border: '1.5px solid #dc2626',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 10, color: '#dc2626', flexShrink: 0,
            }}>✓</span>
            <span style={{ color: '#d1d5db', fontSize: '0.85rem' }}>{f}</span>
          </div>
        ))}
      </div>

      {/* Panneau droit — formulaire */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', padding: '48px' }}>
        <div style={{ width: '100%', maxWidth: 420 }}>

          {/* Badge initialisation */}
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            background: '#fef3c7', border: '1px solid #fbbf24',
            borderRadius: 20, padding: '5px 14px', marginBottom: 24,
            fontSize: '0.78rem', fontWeight: 700, color: '#92400e',
          }}>
            ⚡ Initialisation du système
          </div>

          <h2 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0d0d0d', marginBottom: 8 }}>
            Créer l'administrateur
          </h2>
          <p style={{ color: '#6b7280', fontSize: '0.875rem', marginBottom: 28 }}>
            Ce compte aura tous les droits pour gérer la plateforme et créer d'autres utilisateurs.
          </p>

          <form onSubmit={handleSubmit}>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>Prénom</label>
                <input style={inputStyle} value={form.first_name} onChange={e => set('first_name', e.target.value)} placeholder="Jean"
                  onFocus={e => e.target.style.borderColor = '#dc2626'}
                  onBlur={e => e.target.style.borderColor = '#e5e7eb'} />
              </div>
              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>Nom</label>
                <input style={inputStyle} value={form.last_name} onChange={e => set('last_name', e.target.value)} placeholder="Dupont"
                  onFocus={e => e.target.style.borderColor = '#dc2626'}
                  onBlur={e => e.target.style.borderColor = '#e5e7eb'} />
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>Nom d'utilisateur <span style={{ color: '#dc2626' }}>*</span></label>
              <input style={inputStyle} value={form.username} onChange={e => set('username', e.target.value)} placeholder="admin"
                onFocus={e => e.target.style.borderColor = '#dc2626'}
                onBlur={e => e.target.style.borderColor = '#e5e7eb'} />
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>Email <span style={{ color: '#dc2626' }}>*</span></label>
              <input type="email" style={inputStyle} value={form.email} onChange={e => set('email', e.target.value)} placeholder="admin@entreprise.com"
                onFocus={e => e.target.style.borderColor = '#dc2626'}
                onBlur={e => e.target.style.borderColor = '#e5e7eb'} />
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>Mot de passe <span style={{ color: '#dc2626' }}>*</span></label>
              <input type="password" style={inputStyle} value={form.password} onChange={e => set('password', e.target.value)} placeholder="Min. 6 caractères"
                onFocus={e => e.target.style.borderColor = '#dc2626'}
                onBlur={e => e.target.style.borderColor = '#e5e7eb'} />
            </div>

            <div style={{ marginBottom: 24 }}>
              <label style={labelStyle}>Confirmer le mot de passe <span style={{ color: '#dc2626' }}>*</span></label>
              <input type="password" style={inputStyle} value={form.confirm} onChange={e => set('confirm', e.target.value)} placeholder="••••••••"
                onFocus={e => e.target.style.borderColor = '#dc2626'}
                onBlur={e => e.target.style.borderColor = '#e5e7eb'} />
            </div>

            {error && (
              <div style={{
                background: '#fef2f2', border: '1px solid #fecaca',
                color: '#dc2626', padding: '10px 14px',
                borderRadius: 8, marginBottom: 20,
                fontSize: '0.875rem', display: 'flex', alignItems: 'center', gap: 8,
              }}>
                ⚠ {error}
              </div>
            )}

            <button type="submit" disabled={loading} style={{
              width: '100%', padding: '13px', borderRadius: 8, border: 'none',
              background: loading ? '#9ca3af' : '#dc2626',
              color: '#fff', fontSize: '0.95rem', fontWeight: 700,
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            }}>
              {loading ? 'Création en cours…' : 'Créer l\'administrateur →'}
            </button>
          </form>

          <p style={{ textAlign: 'center', marginTop: 24, fontSize: '0.75rem', color: '#9ca3af' }}>
            Ce formulaire disparaît automatiquement une fois le compte créé.
          </p>
        </div>
      </div>
    </div>
  );
}
