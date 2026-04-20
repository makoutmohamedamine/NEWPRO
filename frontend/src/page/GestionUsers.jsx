import { useState, useEffect } from 'react';
import { getUsers, createUser, updateUser, deleteUser, toggleUserActive } from '../api/api';

const ROLE_LABELS = { admin: 'Administrateur', recruteur: 'Recruteur RH' };
const ROLE_COLORS = { admin: '#7c3aed', recruteur: '#0891b2' };

function Badge({ role }) {
  return (
    <span style={{
      background: ROLE_COLORS[role] + '18',
      color: ROLE_COLORS[role],
      border: `1px solid ${ROLE_COLORS[role]}40`,
      borderRadius: 20, padding: '3px 10px',
      fontSize: '0.75rem', fontWeight: 700, letterSpacing: 0.3,
    }}>
      {ROLE_LABELS[role] || role}
    </span>
  );
}

function Modal({ title, onClose, children }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(3px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div style={{
        background: '#fff', borderRadius: 16, padding: 32,
        width: '100%', maxWidth: 460, boxShadow: '0 20px 60px rgba(0,0,0,0.2)',
        position: 'relative',
      }} onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#111' }}>{title}</h3>
          <button onClick={onClose} style={{
            background: '#f3f4f6', border: 'none', borderRadius: 8,
            width: 32, height: 32, cursor: 'pointer', fontSize: '1rem', color: '#6b7280',
          }}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

function UserForm({ initial = {}, onSave, onCancel, loading }) {
  const [form, setForm] = useState({
    username: initial.username || '',
    email: initial.email || '',
    first_name: initial.first_name || '',
    last_name: initial.last_name || '',
    role: initial.role || 'recruteur',
    password: '',
  });
  const [errors, setErrors] = useState({});

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const validate = () => {
    const e = {};
    if (!form.username.trim()) e.username = 'Requis';
    if (!form.email.trim()) e.email = 'Requis';
    if (!initial.id && !form.password) e.password = 'Requis pour un nouveau compte';
    if (form.password && form.password.length < 6) e.password = 'Minimum 6 caractères';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!validate()) return;
    const payload = { ...form };
    if (!payload.password) delete payload.password;
    onSave(payload);
  };

  const Field = ({ label, name, type = 'text', placeholder, required }) => (
    <div style={{ marginBottom: 16 }}>
      <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#374151', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.4 }}>
        {label}{required && <span style={{ color: '#dc2626' }}> *</span>}
      </label>
      <input
        type={type}
        value={form[name]}
        onChange={e => set(name, e.target.value)}
        placeholder={placeholder}
        style={{
          width: '100%', padding: '10px 12px', borderRadius: 8,
          border: `1.5px solid ${errors[name] ? '#dc2626' : '#e5e7eb'}`,
          fontSize: '0.9rem', boxSizing: 'border-box', outline: 'none',
        }}
        onFocus={e => e.target.style.borderColor = '#dc2626'}
        onBlur={e => e.target.style.borderColor = errors[name] ? '#dc2626' : '#e5e7eb'}
      />
      {errors[name] && <div style={{ color: '#dc2626', fontSize: '0.75rem', marginTop: 4 }}>{errors[name]}</div>}
    </div>
  );

  return (
    <form onSubmit={handleSubmit}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
        <Field label="Prénom" name="first_name" placeholder="Jean" />
        <Field label="Nom" name="last_name" placeholder="Dupont" />
      </div>
      <Field label="Nom d'utilisateur" name="username" placeholder="jean.dupont" required />
      <Field label="Email" name="email" type="email" placeholder="jean@rh.com" required />
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, color: '#374151', marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.4 }}>
          Rôle <span style={{ color: '#dc2626' }}>*</span>
        </label>
        <select
          value={form.role}
          onChange={e => set('role', e.target.value)}
          style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1.5px solid #e5e7eb', fontSize: '0.9rem', boxSizing: 'border-box' }}
        >
          <option value="recruteur">Recruteur RH</option>
          <option value="admin">Administrateur</option>
        </select>
      </div>
      <Field
        label={initial.id ? 'Nouveau mot de passe (laisser vide = inchangé)' : 'Mot de passe'}
        name="password" type="password"
        placeholder={initial.id ? '••••••••' : 'Min. 6 caractères'}
        required={!initial.id}
      />
      <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
        <button type="button" onClick={onCancel} style={{
          flex: 1, padding: '11px', borderRadius: 8, border: '1.5px solid #e5e7eb',
          background: '#fff', color: '#374151', fontWeight: 700, cursor: 'pointer',
        }}>Annuler</button>
        <button type="submit" disabled={loading} style={{
          flex: 2, padding: '11px', borderRadius: 8, border: 'none',
          background: loading ? '#9ca3af' : '#dc2626', color: '#fff',
          fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer', fontSize: '0.9rem',
        }}>
          {loading ? 'Enregistrement…' : (initial.id ? 'Enregistrer les modifications' : 'Créer le compte')}
        </button>
      </div>
    </form>
  );
}

export default function GestionUsers() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [modal, setModal] = useState(null); // null | 'create' | {user}
  const [confirm, setConfirm] = useState(null);
  const [toast, setToast] = useState(null);
  const [search, setSearch] = useState('');

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await getUsers();
      setUsers(data.users);
    } catch {
      showToast('Erreur lors du chargement des utilisateurs', 'error');
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async (payload) => {
    setSaving(true);
    try {
      await createUser(payload);
      showToast(`Compte "${payload.username}" créé avec succès.`);
      setModal(null);
      load();
    } catch (err) {
      showToast(err.response?.data?.errors ? JSON.stringify(err.response.data.errors) : 'Erreur lors de la création', 'error');
    }
    setSaving(false);
  };

  const handleUpdate = async (id, payload) => {
    setSaving(true);
    try {
      await updateUser(id, payload);
      showToast('Compte mis à jour.');
      setModal(null);
      load();
    } catch {
      showToast('Erreur lors de la mise à jour', 'error');
    }
    setSaving(false);
  };

  const handleToggle = async (user) => {
    try {
      await toggleUserActive(user.id);
      showToast(`Compte "${user.username}" ${user.is_active ? 'désactivé' : 'activé'}.`);
      load();
    } catch {
      showToast('Erreur', 'error');
    }
  };

  const handleDelete = async (user) => {
    try {
      await deleteUser(user.id);
      showToast(`Compte "${user.username}" supprimé.`);
      setConfirm(null);
      load();
    } catch {
      showToast('Erreur lors de la suppression', 'error');
    }
  };

  const filtered = users.filter(u =>
    u.username.toLowerCase().includes(search.toLowerCase()) ||
    u.email.toLowerCase().includes(search.toLowerCase()) ||
    (u.first_name + ' ' + u.last_name).toLowerCase().includes(search.toLowerCase())
  );

  const stats = {
    total: users.length,
    admins: users.filter(u => u.role === 'admin').length,
    recruteurs: users.filter(u => u.role === 'recruteur').length,
    actifs: users.filter(u => u.is_active).length,
  };

  return (
    <div style={{ padding: 32, maxWidth: 1100, margin: '0 auto' }}>

      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', top: 24, right: 24, zIndex: 2000,
          background: toast.type === 'error' ? '#fef2f2' : '#f0fdf4',
          border: `1px solid ${toast.type === 'error' ? '#fecaca' : '#bbf7d0'}`,
          color: toast.type === 'error' ? '#dc2626' : '#16a34a',
          borderRadius: 10, padding: '12px 20px',
          boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
          fontWeight: 600, fontSize: '0.875rem',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          {toast.type === 'error' ? '✕' : '✓'} {toast.msg}
        </div>
      )}

      {/* En-tête */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 28 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 800, color: '#111' }}>Gestion des utilisateurs</h1>
          <p style={{ margin: '6px 0 0', color: '#6b7280', fontSize: '0.875rem' }}>
            Créez et gérez les comptes des collaborateurs RH
          </p>
        </div>
        <button onClick={() => setModal('create')} style={{
          background: '#dc2626', color: '#fff', border: 'none',
          borderRadius: 10, padding: '11px 22px', fontWeight: 700,
          fontSize: '0.9rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8,
          boxShadow: '0 4px 12px rgba(220,38,38,0.3)',
        }}>
          + Créer un compte
        </button>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 28 }}>
        {[
          { label: 'Total comptes', value: stats.total, color: '#0f172a' },
          { label: 'Administrateurs', value: stats.admins, color: '#7c3aed' },
          { label: 'Recruteurs RH', value: stats.recruteurs, color: '#0891b2' },
          { label: 'Comptes actifs', value: stats.actifs, color: '#16a34a' },
        ].map(s => (
          <div key={s.label} style={{
            background: '#fff', borderRadius: 12, padding: '18px 20px',
            boxShadow: '0 1px 4px rgba(0,0,0,0.06)', border: '1px solid #f1f5f9',
          }}>
            <div style={{ fontSize: '1.8rem', fontWeight: 800, color: s.color }}>{s.value}</div>
            <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: 2 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Barre de recherche */}
      <div style={{ marginBottom: 20 }}>
        <input
          type="text"
          placeholder="Rechercher un utilisateur…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            width: '100%', maxWidth: 360, padding: '10px 14px',
            borderRadius: 8, border: '1.5px solid #e5e7eb',
            fontSize: '0.9rem', boxSizing: 'border-box', outline: 'none',
          }}
        />
      </div>

      {/* Table des utilisateurs */}
      <div style={{ background: '#fff', borderRadius: 14, boxShadow: '0 1px 4px rgba(0,0,0,0.06)', border: '1px solid #f1f5f9', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e5e7eb' }}>
              {['Utilisateur', 'Email', 'Rôle', 'Statut', 'Inscrit le', 'Actions'].map(h => (
                <th key={h} style={{ padding: '12px 16px', textAlign: 'left', fontSize: '0.75rem', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 0.5 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} style={{ textAlign: 'center', padding: 40, color: '#9ca3af' }}>Chargement…</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={6} style={{ textAlign: 'center', padding: 40, color: '#9ca3af' }}>Aucun utilisateur trouvé</td></tr>
            ) : filtered.map((user, i) => (
              <tr key={user.id} style={{ borderBottom: i < filtered.length - 1 ? '1px solid #f1f5f9' : 'none', transition: 'background 0.15s' }}
                onMouseEnter={e => e.currentTarget.style.background = '#fafafa'}
                onMouseLeave={e => e.currentTarget.style.background = '#fff'}
              >
                <td style={{ padding: '14px 16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{
                      width: 36, height: 36, borderRadius: '50%',
                      background: ROLE_COLORS[user.role] + '20',
                      color: ROLE_COLORS[user.role],
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontWeight: 800, fontSize: '0.85rem', flexShrink: 0,
                    }}>
                      {(user.first_name?.[0] || user.username[0]).toUpperCase()}
                    </div>
                    <div>
                      <div style={{ fontWeight: 700, color: '#111', fontSize: '0.9rem' }}>
                        {user.first_name || user.last_name ? `${user.first_name} ${user.last_name}`.trim() : user.username}
                      </div>
                      <div style={{ color: '#9ca3af', fontSize: '0.78rem' }}>@{user.username}</div>
                    </div>
                  </div>
                </td>
                <td style={{ padding: '14px 16px', color: '#374151', fontSize: '0.875rem' }}>{user.email}</td>
                <td style={{ padding: '14px 16px' }}><Badge role={user.role} /></td>
                <td style={{ padding: '14px 16px' }}>
                  <span style={{
                    background: user.is_active ? '#f0fdf4' : '#fef2f2',
                    color: user.is_active ? '#16a34a' : '#dc2626',
                    border: `1px solid ${user.is_active ? '#bbf7d0' : '#fecaca'}`,
                    borderRadius: 20, padding: '3px 10px',
                    fontSize: '0.75rem', fontWeight: 700,
                  }}>
                    {user.is_active ? 'Actif' : 'Désactivé'}
                  </span>
                </td>
                <td style={{ padding: '14px 16px', color: '#6b7280', fontSize: '0.8rem' }}>
                  {new Date(user.date_joined).toLocaleDateString('fr-FR')}
                </td>
                <td style={{ padding: '14px 16px' }}>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button onClick={() => setModal(user)} title="Modifier" style={{
                      background: '#f3f4f6', border: 'none', borderRadius: 7,
                      padding: '6px 10px', cursor: 'pointer', fontSize: '0.8rem', color: '#374151',
                    }}>✏️</button>
                    <button onClick={() => handleToggle(user)} title={user.is_active ? 'Désactiver' : 'Activer'} style={{
                      background: user.is_active ? '#fef3c7' : '#f0fdf4',
                      border: 'none', borderRadius: 7, padding: '6px 10px',
                      cursor: 'pointer', fontSize: '0.8rem',
                    }}>
                      {user.is_active ? '⏸' : '▶'}
                    </button>
                    <button onClick={() => setConfirm(user)} title="Supprimer" style={{
                      background: '#fef2f2', border: 'none', borderRadius: 7,
                      padding: '6px 10px', cursor: 'pointer', fontSize: '0.8rem',
                    }}>🗑️</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal Créer */}
      {modal === 'create' && (
        <Modal title="Créer un compte utilisateur" onClose={() => setModal(null)}>
          <UserForm
            onSave={handleCreate}
            onCancel={() => setModal(null)}
            loading={saving}
          />
        </Modal>
      )}

      {/* Modal Modifier */}
      {modal && modal !== 'create' && (
        <Modal title={`Modifier — ${modal.username}`} onClose={() => setModal(null)}>
          <UserForm
            initial={modal}
            onSave={(payload) => handleUpdate(modal.id, payload)}
            onCancel={() => setModal(null)}
            loading={saving}
          />
        </Modal>
      )}

      {/* Modal Confirmation suppression */}
      {confirm && (
        <Modal title="Confirmer la suppression" onClose={() => setConfirm(null)}>
          <p style={{ color: '#374151', marginBottom: 24 }}>
            Êtes-vous sûr de vouloir supprimer le compte <strong>@{confirm.username}</strong> ?<br />
            <span style={{ color: '#dc2626', fontSize: '0.875rem' }}>Cette action est irréversible.</span>
          </p>
          <div style={{ display: 'flex', gap: 12 }}>
            <button onClick={() => setConfirm(null)} style={{
              flex: 1, padding: '11px', borderRadius: 8, border: '1.5px solid #e5e7eb',
              background: '#fff', fontWeight: 700, cursor: 'pointer',
            }}>Annuler</button>
            <button onClick={() => handleDelete(confirm)} style={{
              flex: 1, padding: '11px', borderRadius: 8, border: 'none',
              background: '#dc2626', color: '#fff', fontWeight: 700, cursor: 'pointer',
            }}>Supprimer</button>
          </div>
        </Modal>
      )}
    </div>
  );
}
