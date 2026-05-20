import { useState, useEffect, useCallback } from 'react';
import { getUsers, getAdminStats, createUser, updateUser, deleteUser, toggleUserActive } from '../api/api';

// ── Constantes ────────────────────────────────────────────────────────────────

const ROLES = [
  { value: 'admin',     label: 'Administrateur',  color: '#7c3aed', bg: '#ede9fe' },
  { value: 'rh',        label: 'Responsable RH',  color: '#0891b2', bg: '#e0f2fe' },
  { value: 'recruteur', label: 'Recruteur',        color: '#059669', bg: '#d1fae5' },
  { value: 'manager',   label: 'Manager',          color: '#d97706', bg: '#fef3c7' },
];

const getRoleInfo = (role) => ROLES.find(r => r.value === role) || { label: role, color: '#6b7280', bg: '#f3f4f6' };

const TABS = [
  { id: 'overview', label: 'Vue d\'ensemble', icon: '📊' },
  { id: 'users',    label: 'Comptes',          icon: '👥' },
  { id: 'activity', label: 'Activité',         icon: '📈' },
];

// ── Composants ────────────────────────────────────────────────────────────────

function Avatar({ user, size = 38 }) {
  const info = getRoleInfo(user.role);
  const initials = (user.first_name?.[0] || user.username?.[0] || '?').toUpperCase();
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%', flexShrink: 0,
      background: info.bg, color: info.color,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontWeight: 800, fontSize: size * 0.38,
      border: `2px solid ${info.color}30`,
    }}>
      {initials}
    </div>
  );
}

function RoleBadge({ role }) {
  const info = getRoleInfo(role);
  return (
    <span style={{
      background: info.bg, color: info.color,
      border: `1px solid ${info.color}40`,
      borderRadius: 20, padding: '3px 10px',
      fontSize: '0.73rem', fontWeight: 700, letterSpacing: 0.3, whiteSpace: 'nowrap',
    }}>
      {info.label}
    </span>
  );
}

function StatusBadge({ active }) {
  return (
    <span style={{
      background: active ? '#f0fdf4' : '#fef2f2',
      color: active ? '#16a34a' : '#dc2626',
      border: `1px solid ${active ? '#bbf7d0' : '#fecaca'}`,
      borderRadius: 20, padding: '3px 10px',
      fontSize: '0.73rem', fontWeight: 700,
    }}>
      {active ? '● Actif' : '○ Désactivé'}
    </span>
  );
}

function Toast({ toast }) {
  if (!toast) return null;
  const isError = toast.type === 'error';
  return (
    <div style={{
      position: 'fixed', top: 24, right: 24, zIndex: 3000,
      background: isError ? '#fef2f2' : '#f0fdf4',
      border: `1px solid ${isError ? '#fecaca' : '#bbf7d0'}`,
      color: isError ? '#dc2626' : '#16a34a',
      borderRadius: 12, padding: '14px 20px',
      boxShadow: '0 8px 32px rgba(0,0,0,0.14)',
      fontWeight: 600, fontSize: '0.875rem',
      display: 'flex', alignItems: 'center', gap: 10,
      maxWidth: 400, animation: 'slideIn 0.25s ease',
    }}>
      <span style={{ fontSize: '1.1rem' }}>{isError ? '⚠' : '✓'}</span>
      {toast.msg}
    </div>
  );
}

function Modal({ title, subtitle, onClose, children, wide = false }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 2000,
      background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
    }} onClick={onClose}>
      <div style={{
        background: '#fff', borderRadius: 18, padding: '28px 32px',
        width: '100%', maxWidth: wide ? 620 : 480,
        boxShadow: '0 24px 80px rgba(0,0,0,0.18)',
        maxHeight: '90vh', overflowY: 'auto',
      }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#111' }}>{title}</h3>
            {subtitle && <p style={{ margin: '4px 0 0', color: '#6b7280', fontSize: '0.82rem' }}>{subtitle}</p>}
          </div>
          <button onClick={onClose} style={{
            background: '#f3f4f6', border: 'none', borderRadius: 8,
            width: 34, height: 34, cursor: 'pointer', fontSize: '1rem',
            color: '#6b7280', display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

function FormField({ label, name, type = 'text', value, onChange, error, placeholder, required, children }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{
        display: 'block', fontSize: '0.76rem', fontWeight: 700,
        color: '#374151', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.5,
      }}>
        {label}{required && <span style={{ color: '#dc2626', marginLeft: 2 }}>*</span>}
      </label>
      {children || (
        <input
          type={type}
          value={value}
          onChange={e => onChange(name, e.target.value)}
          placeholder={placeholder}
          style={{
            width: '100%', padding: '10px 12px', borderRadius: 8, boxSizing: 'border-box',
            border: `1.5px solid ${error ? '#dc2626' : '#e5e7eb'}`,
            fontSize: '0.9rem', outline: 'none', transition: 'border-color 0.15s',
          }}
          onFocus={e => e.target.style.borderColor = '#b42318'}
          onBlur={e => e.target.style.borderColor = error ? '#dc2626' : '#e5e7eb'}
        />
      )}
      {error && <p style={{ color: '#dc2626', fontSize: '0.75rem', margin: '4px 0 0' }}>{error}</p>}
    </div>
  );
}

function UserForm({ initial = {}, onSave, onCancel, loading }) {
  const isEdit = Boolean(initial.id);
  const [form, setForm] = useState({
    username:   initial.username   || '',
    email:      initial.email      || '',
    first_name: initial.first_name || '',
    last_name:  initial.last_name  || '',
    role:       initial.role       || 'recruteur',
    is_active:  initial.is_active  !== undefined ? initial.is_active : true,
    password:   '',
    password2:  '',
  });
  const [errors, setErrors] = useState({});

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const validate = () => {
    const e = {};
    if (!form.username.trim()) e.username = 'Nom d\'utilisateur requis';
    if (!form.email.trim()) e.email = 'Email requis';
    if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) e.email = 'Email invalide';
    if (!isEdit && !form.password) e.password = 'Mot de passe requis';
    if (form.password && form.password.length < 6) e.password = 'Minimum 6 caractères';
    if (form.password && form.password !== form.password2) e.password2 = 'Les mots de passe ne correspondent pas';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!validate()) return;
    const payload = {
      username: form.username.trim(),
      email: form.email.trim(),
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      role: form.role,
      is_active: form.is_active,
    };
    if (form.password) payload.password = form.password;
    onSave(payload);
  };

  return (
    <form onSubmit={handleSubmit}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
        <FormField label="Prénom" name="first_name" value={form.first_name} onChange={set} placeholder="Jean" />
        <FormField label="Nom" name="last_name" value={form.last_name} onChange={set} placeholder="Dupont" />
      </div>
      <FormField label="Nom d'utilisateur" name="username" value={form.username} onChange={set}
        placeholder="jean.dupont" required error={errors.username} />
      <FormField label="Adresse email" name="email" type="email" value={form.email} onChange={set}
        placeholder="jean@entreprise.com" required error={errors.email} />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
        <FormField label="Rôle" name="role" value={form.role} onChange={set} required>
          <select value={form.role} onChange={e => set('role', e.target.value)} style={{
            width: '100%', padding: '10px 12px', borderRadius: 8, boxSizing: 'border-box',
            border: '1.5px solid #e5e7eb', fontSize: '0.9rem', background: '#fff',
          }}>
            {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </FormField>
        <FormField label="Statut" name="is_active" value={form.is_active} onChange={set}>
          <select value={form.is_active ? 'true' : 'false'} onChange={e => set('is_active', e.target.value === 'true')} style={{
            width: '100%', padding: '10px 12px', borderRadius: 8, boxSizing: 'border-box',
            border: '1.5px solid #e5e7eb', fontSize: '0.9rem', background: '#fff',
          }}>
            <option value="true">Actif</option>
            <option value="false">Désactivé</option>
          </select>
        </FormField>
      </div>

      <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: 16, marginTop: 4 }}>
        <p style={{ margin: '0 0 14px', fontSize: '0.78rem', color: '#6b7280', fontWeight: 600 }}>
          {isEdit ? 'MOT DE PASSE (laisser vide pour ne pas changer)' : 'MOT DE PASSE *'}
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
          <FormField label="Mot de passe" name="password" type="password" value={form.password} onChange={set}
            placeholder="••••••••" error={errors.password} required={!isEdit} />
          <FormField label="Confirmer" name="password2" type="password" value={form.password2} onChange={set}
            placeholder="••••••••" error={errors.password2} />
        </div>
      </div>

      {/* Aperçu du profil */}
      <div style={{
        background: '#f8fafc', borderRadius: 10, padding: '12px 16px',
        marginBottom: 20, display: 'flex', alignItems: 'center', gap: 12, border: '1px solid #e5e7eb',
      }}>
        <Avatar user={form} size={42} />
        <div>
          <div style={{ fontWeight: 700, color: '#111', fontSize: '0.9rem' }}>
            {[form.first_name, form.last_name].filter(Boolean).join(' ') || form.username || 'Aperçu...'}
          </div>
          <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
            <RoleBadge role={form.role} />
            <StatusBadge active={form.is_active} />
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12 }}>
        <button type="button" onClick={onCancel} style={{
          flex: 1, padding: '11px', borderRadius: 8, border: '1.5px solid #e5e7eb',
          background: '#fff', color: '#374151', fontWeight: 700, cursor: 'pointer', fontSize: '0.9rem',
        }}>Annuler</button>
        <button type="submit" disabled={loading} style={{
          flex: 2, padding: '11px', borderRadius: 8, border: 'none',
          background: loading ? '#9ca3af' : '#b42318', color: '#fff',
          fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer', fontSize: '0.9rem',
        }}>
          {loading ? 'Enregistrement…' : (isEdit ? 'Enregistrer les modifications' : 'Créer le compte')}
        </button>
      </div>
    </form>
  );
}

// ── Page principale ───────────────────────────────────────────────────────────

export default function GestionUsers() {
  const [tab, setTab] = useState('overview');
  const [users, setUsers] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [modal, setModal] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [toast, setToast] = useState(null);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const showToast = useCallback((msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [usersRes, statsRes] = await Promise.all([getUsers(), getAdminStats()]);
      setUsers(usersRes.data?.users || []);
      setStats(statsRes.data || null);
    } catch {
      showToast('Erreur de chargement', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const handleCreate = async (payload) => {
    setSaving(true);
    try {
      await createUser(payload);
      showToast(`Compte "${payload.username}" créé avec succès.`);
      setModal(null);
      loadAll();
    } catch (err) {
      const msg = err.response?.data?.errors
        ? Object.values(err.response.data.errors).flat().join(', ')
        : 'Erreur lors de la création';
      showToast(msg, 'error');
    } finally { setSaving(false); }
  };

  const handleUpdate = async (id, payload) => {
    setSaving(true);
    try {
      await updateUser(id, payload);
      showToast('Compte mis à jour avec succès.');
      setModal(null);
      loadAll();
    } catch (err) {
      const msg = err.response?.data?.errors
        ? Object.values(err.response.data.errors).flat().join(', ')
        : 'Erreur lors de la mise à jour';
      showToast(msg, 'error');
    } finally { setSaving(false); }
  };

  const handleToggle = async (user) => {
    try {
      await toggleUserActive(user.id);
      showToast(`Compte "${user.username}" ${user.is_active ? 'désactivé' : 'réactivé'}.`);
      loadAll();
    } catch { showToast('Erreur', 'error'); }
  };

  const handleDelete = async () => {
    if (!confirmDelete) return;
    try {
      await deleteUser(confirmDelete.id);
      showToast(`Compte "${confirmDelete.username}" supprimé.`);
      setConfirmDelete(null);
      loadAll();
    } catch { showToast('Erreur lors de la suppression', 'error'); }
  };

  // Filtrage
  const filtered = users.filter(u => {
    const q = search.toLowerCase();
    const matchSearch = !q || u.username.toLowerCase().includes(q)
      || u.email.toLowerCase().includes(q)
      || `${u.first_name} ${u.last_name}`.toLowerCase().includes(q);
    const matchRole = !roleFilter || u.role === roleFilter;
    const matchStatus = !statusFilter
      || (statusFilter === 'active' && u.is_active)
      || (statusFilter === 'inactive' && !u.is_active);
    return matchSearch && matchRole && matchStatus;
  });

  const s = stats?.users || {};
  const sys = stats?.system || {};
  const activity = stats?.activity || [];

  return (
    <div style={{ minHeight: '100vh', background: '#f8fafc' }}>
      <Toast toast={toast} />

      {/* En-tête */}
      <div style={{
        background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #b42318 100%)',
        padding: '28px 32px 0', color: '#fff',
      }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', letterSpacing: 1, marginBottom: 4 }}>
                ESPACE ADMINISTRATEUR
              </div>
              <h1 style={{ margin: 0, fontSize: '1.6rem', fontWeight: 800 }}>Gestion des utilisateurs</h1>
              <p style={{ margin: '6px 0 0', color: '#94a3b8', fontSize: '0.875rem' }}>
                Créez, supervisez et gérez tous les comptes de votre espace RH
              </p>
            </div>
            <button onClick={() => setModal('create')} style={{
              background: '#b42318', color: '#fff', border: 'none',
              borderRadius: 10, padding: '11px 22px', fontWeight: 700,
              fontSize: '0.9rem', cursor: 'pointer',
              boxShadow: '0 4px 16px rgba(180,35,24,0.4)',
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              + Nouveau compte
            </button>
          </div>

          {/* Onglets */}
          <div style={{ display: 'flex', gap: 4 }}>
            {TABS.map(t => (
              <button key={t.id} onClick={() => setTab(t.id)} style={{
                padding: '10px 20px', border: 'none', cursor: 'pointer',
                borderRadius: '8px 8px 0 0', fontWeight: 700, fontSize: '0.85rem',
                background: tab === t.id ? '#fff' : 'transparent',
                color: tab === t.id ? '#b42318' : '#94a3b8',
                transition: 'all 0.15s',
              }}>
                <span style={{ marginRight: 6 }}>{t.icon}</span>{t.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '28px 32px' }}>

        {loading ? (
          <div style={{ textAlign: 'center', padding: 80, color: '#6b7280' }}>
            <div style={{ fontSize: '2rem', marginBottom: 12 }}>⏳</div>
            Chargement…
          </div>
        ) : (
          <>
            {/* ── TAB: Vue d'ensemble ── */}
            {tab === 'overview' && (
              <div>
                {/* KPI Cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 28 }}>
                  {[
                    { label: 'Total comptes', value: s.total || 0, icon: '👥', color: '#0f172a', sub: `${s.new_30d || 0} ce mois` },
                    { label: 'Comptes actifs', value: s.active || 0, icon: '✅', color: '#16a34a', sub: `${s.inactive || 0} désactivé(s)` },
                    { label: 'Nouveaux (7j)', value: s.new_7d || 0, icon: '🆕', color: '#0891b2', sub: `${s.new_30d || 0} sur 30 jours` },
                    { label: 'Candidats total', value: sys.total_candidates || 0, icon: '📄', color: '#7c3aed', sub: `${sys.candidates_30d || 0} ce mois` },
                  ].map(k => (
                    <div key={k.label} style={{
                      background: '#fff', borderRadius: 14, padding: '20px 22px',
                      boxShadow: '0 1px 4px rgba(0,0,0,0.06)', border: '1px solid #e5e7eb',
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                          <div style={{ fontSize: '2rem', fontWeight: 800, color: k.color, lineHeight: 1 }}>{k.value}</div>
                          <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: 4 }}>{k.label}</div>
                          <div style={{ fontSize: '0.72rem', color: '#9ca3af', marginTop: 2 }}>{k.sub}</div>
                        </div>
                        <span style={{ fontSize: '1.6rem' }}>{k.icon}</span>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Répartition par rôle */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 28 }}>
                  <div style={{ background: '#fff', borderRadius: 14, padding: '22px 24px', border: '1px solid #e5e7eb' }}>
                    <h3 style={{ margin: '0 0 18px', fontSize: '0.95rem', fontWeight: 800, color: '#111' }}>
                      Répartition par rôle
                    </h3>
                    {ROLES.map(role => {
                      const count = s.by_role?.[role.value]?.count || 0;
                      const pct = s.total ? Math.round((count / s.total) * 100) : 0;
                      return (
                        <div key={role.value} style={{ marginBottom: 14 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <div style={{ width: 10, height: 10, borderRadius: '50%', background: role.color }} />
                              <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#374151' }}>{role.label}</span>
                            </div>
                            <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#111' }}>
                              {count} <span style={{ color: '#9ca3af', fontWeight: 400 }}>({pct}%)</span>
                            </span>
                          </div>
                          <div style={{ height: 6, background: '#f1f5f9', borderRadius: 3, overflow: 'hidden' }}>
                            <div style={{ width: `${pct}%`, height: '100%', background: role.color, borderRadius: 3, transition: 'width 0.5s' }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <div style={{ background: '#fff', borderRadius: 14, padding: '22px 24px', border: '1px solid #e5e7eb' }}>
                    <h3 style={{ margin: '0 0 18px', fontSize: '0.95rem', fontWeight: 800, color: '#111' }}>
                      Statistiques système
                    </h3>
                    {[
                      { label: 'Candidats enregistrés', value: sys.total_candidates || 0, icon: '👤', color: '#7c3aed' },
                      { label: 'Postes créés', value: sys.total_postes || 0, icon: '💼', color: '#0891b2' },
                      { label: 'Candidatures traitées', value: sys.total_candidatures || 0, icon: '📋', color: '#059669' },
                      { label: 'Activité ce mois', value: (sys.candidates_30d || 0) + (sys.candidatures_30d || 0), icon: '📈', color: '#d97706' },
                    ].map(item => (
                      <div key={item.label} style={{
                        display: 'flex', alignItems: 'center', gap: 12,
                        padding: '10px 0', borderBottom: '1px solid #f1f5f9',
                      }}>
                        <div style={{
                          width: 36, height: 36, borderRadius: 8,
                          background: item.color + '15', color: item.color,
                          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.1rem',
                        }}>{item.icon}</div>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>{item.label}</div>
                        </div>
                        <div style={{ fontSize: '1.3rem', fontWeight: 800, color: item.color }}>{item.value}</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Liste rapide des comptes */}
                <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e5e7eb', overflow: 'hidden' }}>
                  <div style={{ padding: '18px 22px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 800, color: '#111' }}>Comptes récents</h3>
                    <button onClick={() => setTab('users')} style={{
                      background: 'none', border: 'none', color: '#b42318', fontWeight: 700,
                      fontSize: '0.82rem', cursor: 'pointer',
                    }}>Voir tout →</button>
                  </div>
                  <div style={{ padding: '8px 0' }}>
                    {users.slice(0, 6).map(u => (
                      <div key={u.id} style={{
                        display: 'flex', alignItems: 'center', gap: 12,
                        padding: '10px 22px', borderBottom: '1px solid #f9fafb',
                      }}>
                        <Avatar user={u} size={36} />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: '0.875rem', fontWeight: 700, color: '#111' }}>
                            {u.first_name || u.last_name ? `${u.first_name} ${u.last_name}`.trim() : u.username}
                          </div>
                          <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>@{u.username} · {u.email}</div>
                        </div>
                        <RoleBadge role={u.role} />
                        <StatusBadge active={u.is_active} />
                        <div style={{ fontSize: '0.75rem', color: '#9ca3af', minWidth: 80, textAlign: 'right' }}>
                          {new Date(u.date_joined).toLocaleDateString('fr-FR')}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* ── TAB: Comptes ── */}
            {tab === 'users' && (
              <div>
                {/* Barre de filtres */}
                <div style={{
                  background: '#fff', borderRadius: 14, padding: '16px 20px',
                  marginBottom: 20, border: '1px solid #e5e7eb',
                  display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center',
                }}>
                  <input
                    type="text" placeholder="🔍  Rechercher par nom, email, username…"
                    value={search} onChange={e => setSearch(e.target.value)}
                    style={{
                      flex: 1, minWidth: 220, padding: '9px 14px', borderRadius: 8,
                      border: '1.5px solid #e5e7eb', fontSize: '0.875rem', outline: 'none',
                    }}
                  />
                  <select value={roleFilter} onChange={e => setRoleFilter(e.target.value)} style={{
                    padding: '9px 12px', borderRadius: 8, border: '1.5px solid #e5e7eb',
                    fontSize: '0.875rem', background: '#fff', minWidth: 150,
                  }}>
                    <option value="">Tous les rôles</option>
                    {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                  </select>
                  <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{
                    padding: '9px 12px', borderRadius: 8, border: '1.5px solid #e5e7eb',
                    fontSize: '0.875rem', background: '#fff', minWidth: 140,
                  }}>
                    <option value="">Tous les statuts</option>
                    <option value="active">Actifs</option>
                    <option value="inactive">Désactivés</option>
                  </select>
                  <div style={{ fontSize: '0.8rem', color: '#6b7280', marginLeft: 'auto' }}>
                    {filtered.length} résultat{filtered.length !== 1 ? 's' : ''}
                  </div>
                </div>

                {/* Table */}
                <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e5e7eb', overflow: 'hidden' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ background: '#f8fafc' }}>
                        {['Utilisateur', 'Rôle', 'Statut', 'Activité', 'Dernière connexion', 'Créé le', 'Actions'].map(h => (
                          <th key={h} style={{
                            padding: '12px 16px', textAlign: 'left', fontSize: '0.72rem',
                            fontWeight: 700, color: '#6b7280', textTransform: 'uppercase',
                            letterSpacing: 0.5, borderBottom: '1px solid #e5e7eb', whiteSpace: 'nowrap',
                          }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.length === 0 ? (
                        <tr>
                          <td colSpan={7} style={{ textAlign: 'center', padding: 48, color: '#9ca3af' }}>
                            Aucun utilisateur correspondant aux filtres
                          </td>
                        </tr>
                      ) : filtered.map((user, i) => (
                        <tr key={user.id}
                          style={{ borderBottom: i < filtered.length - 1 ? '1px solid #f8fafc' : 'none', transition: 'background 0.1s' }}
                          onMouseEnter={e => e.currentTarget.style.background = '#fafafa'}
                          onMouseLeave={e => e.currentTarget.style.background = '#fff'}
                        >
                          <td style={{ padding: '14px 16px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                              <Avatar user={user} size={36} />
                              <div>
                                <div style={{ fontWeight: 700, fontSize: '0.875rem', color: '#111' }}>
                                  {user.first_name || user.last_name
                                    ? `${user.first_name} ${user.last_name}`.trim()
                                    : user.username}
                                </div>
                                <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>@{user.username} · {user.email}</div>
                              </div>
                            </div>
                          </td>
                          <td style={{ padding: '14px 16px' }}><RoleBadge role={user.role} /></td>
                          <td style={{ padding: '14px 16px' }}><StatusBadge active={user.is_active} /></td>
                          <td style={{ padding: '14px 16px' }}>
                            <div style={{ fontSize: '0.75rem', color: '#374151' }}>
                              <span style={{ color: '#7c3aed', fontWeight: 700 }}>{user.candidates_count || 0}</span> candidats ·{' '}
                              <span style={{ color: '#0891b2', fontWeight: 700 }}>{user.postes_count || 0}</span> postes
                            </div>
                          </td>
                          <td style={{ padding: '14px 16px', fontSize: '0.78rem', color: '#6b7280', whiteSpace: 'nowrap' }}>
                            {user.last_login_display || '—'}
                          </td>
                          <td style={{ padding: '14px 16px', fontSize: '0.78rem', color: '#6b7280', whiteSpace: 'nowrap' }}>
                            {new Date(user.date_joined).toLocaleDateString('fr-FR')}
                          </td>
                          <td style={{ padding: '14px 16px' }}>
                            <div style={{ display: 'flex', gap: 6 }}>
                              <button onClick={() => setModal(user)} title="Modifier"
                                style={{ background: '#f3f4f6', border: 'none', borderRadius: 7, padding: '7px 10px', cursor: 'pointer', fontSize: '0.85rem' }}>
                                ✏️
                              </button>
                              <button onClick={() => handleToggle(user)}
                                title={user.is_active ? 'Désactiver' : 'Réactiver'}
                                style={{ background: user.is_active ? '#fef3c7' : '#f0fdf4', border: 'none', borderRadius: 7, padding: '7px 10px', cursor: 'pointer', fontSize: '0.85rem' }}>
                                {user.is_active ? '⏸' : '▶'}
                              </button>
                              <button onClick={() => setConfirmDelete(user)} title="Supprimer"
                                style={{ background: '#fef2f2', border: 'none', borderRadius: 7, padding: '7px 10px', cursor: 'pointer', fontSize: '0.85rem' }}>
                                🗑️
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* ── TAB: Activité ── */}
            {tab === 'activity' && (
              <div>
                <div style={{ marginBottom: 16, fontSize: '0.82rem', color: '#6b7280' }}>
                  Activité cumulée par utilisateur — candidats, postes et candidatures créés
                </div>
                <div style={{ display: 'grid', gap: 14 }}>
                  {activity.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: 48, color: '#9ca3af', background: '#fff', borderRadius: 14 }}>
                      Aucune donnée d'activité disponible
                    </div>
                  ) : activity.sort((a, b) => (b.candidates_total + b.postes_total) - (a.candidates_total + a.postes_total)).map(u => {
                    const total = u.candidates_total + u.postes_total + u.candidatures_total;
                    const maxTotal = Math.max(...activity.map(x => x.candidates_total + x.postes_total + x.candidatures_total), 1);
                    const pct = Math.round((total / maxTotal) * 100);
                    return (
                      <div key={u.id} style={{
                        background: '#fff', borderRadius: 14, padding: '18px 22px',
                        border: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', gap: 16,
                      }}>
                        <Avatar user={u} size={44} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
                            <span style={{ fontWeight: 700, fontSize: '0.9rem', color: '#111' }}>{u.full_name}</span>
                            <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>@{u.username}</span>
                            <RoleBadge role={u.role} />
                            <StatusBadge active={u.is_active} />
                          </div>
                          <div style={{ height: 8, background: '#f1f5f9', borderRadius: 4, marginBottom: 8, overflow: 'hidden' }}>
                            <div style={{ width: `${pct}%`, height: '100%', background: 'linear-gradient(90deg, #b42318, #7c3aed)', borderRadius: 4, transition: 'width 0.6s' }} />
                          </div>
                          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
                            {[
                              { label: 'Candidats', value: u.candidates_total, color: '#7c3aed', sub: `${u.candidates_30d} ce mois` },
                              { label: 'Postes', value: u.postes_total, color: '#0891b2', sub: '' },
                              { label: 'Candidatures', value: u.candidatures_total, color: '#059669', sub: '' },
                              { label: 'Dernière connexion', value: u.last_login || 'Jamais', color: '#6b7280', sub: '' },
                            ].map(item => (
                              <div key={item.label}>
                                <div style={{ fontSize: '0.72rem', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: 0.4 }}>{item.label}</div>
                                <div style={{ fontSize: '0.95rem', fontWeight: 800, color: item.color }}>{item.value}</div>
                                {item.sub && <div style={{ fontSize: '0.68rem', color: '#9ca3af' }}>{item.sub}</div>}
                              </div>
                            ))}
                          </div>
                        </div>
                        <button onClick={() => setModal(users.find(x => x.id === u.id) || u)} style={{
                          background: '#f3f4f6', border: 'none', borderRadius: 8,
                          padding: '8px 14px', cursor: 'pointer', fontWeight: 600,
                          fontSize: '0.8rem', color: '#374151', whiteSpace: 'nowrap',
                        }}>
                          Modifier ✏️
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* ── Modals ── */}

      {modal === 'create' && (
        <Modal title="Créer un compte utilisateur" subtitle="Remplissez tous les champs requis" onClose={() => setModal(null)}>
          <UserForm onSave={handleCreate} onCancel={() => setModal(null)} loading={saving} />
        </Modal>
      )}

      {modal && modal !== 'create' && (
        <Modal
          title={`Modifier le compte`}
          subtitle={`@${modal.username} — ${getRoleInfo(modal.role).label}`}
          onClose={() => setModal(null)}
        >
          <UserForm initial={modal} onSave={p => handleUpdate(modal.id, p)} onCancel={() => setModal(null)} loading={saving} />
        </Modal>
      )}

      {confirmDelete && (
        <Modal title="Confirmer la suppression" onClose={() => setConfirmDelete(null)}>
          <div style={{
            background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 10,
            padding: '14px 16px', marginBottom: 20,
          }}>
            <p style={{ margin: 0, color: '#374151', fontSize: '0.9rem' }}>
              Vous êtes sur le point de supprimer définitivement le compte :<br />
              <strong style={{ color: '#b42318' }}>@{confirmDelete.username}</strong>
              {confirmDelete.email ? ` (${confirmDelete.email})` : ''}
            </p>
            <p style={{ margin: '8px 0 0', color: '#dc2626', fontSize: '0.8rem', fontWeight: 600 }}>
              ⚠ Cette action est irréversible. Toutes les données liées seront dissociées.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <button onClick={() => setConfirmDelete(null)} style={{
              flex: 1, padding: '11px', borderRadius: 8, border: '1.5px solid #e5e7eb',
              background: '#fff', fontWeight: 700, cursor: 'pointer',
            }}>Annuler</button>
            <button onClick={handleDelete} style={{
              flex: 1, padding: '11px', borderRadius: 8, border: 'none',
              background: '#dc2626', color: '#fff', fontWeight: 700, cursor: 'pointer',
            }}>Supprimer définitivement</button>
          </div>
        </Modal>
      )}

      <style>{`
        @keyframes slideIn {
          from { opacity: 0; transform: translateX(20px); }
          to { opacity: 1; transform: translateX(0); }
        }
      `}</style>
    </div>
  );
}
