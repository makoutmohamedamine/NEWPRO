import { useEffect, useState } from 'react';
import { getPostes, createPoste, updatePoste, deletePoste } from '../api/api';

const FIELDS = [
  { key: 'titre',               label: 'Titre du poste',       rows: 1 },
  { key: 'description',         label: 'Description',          rows: 3 },
  { key: 'competences_requises', label: 'Compétences requises (séparées par virgule)', rows: 2 },
];

const EMPTY = { titre: '', description: '', competences_requises: '' };

export default function Postes() {
  const [postes, setPostes]       = useState([]);
  const [form, setForm]           = useState(EMPTY);
  const [saving, setSaving]       = useState(false);
  const [loading, setLoading]     = useState(true);
  const [showForm, setShowForm]   = useState(false);
  const [editId, setEditId]       = useState(null);
  const [editForm, setEditForm]   = useState(EMPTY);
  const [editSaving, setEditSaving] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null); // poste à confirmer

  const load = () => getPostes().then(r => setPostes(r.data)).finally(() => setLoading(false));

  useEffect(() => { load(); }, []);

  // ── Créer un poste ────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!form.titre.trim() || !form.description.trim()) return;
    setSaving(true);
    try {
      await createPoste(form);
      setForm(EMPTY);
      setShowForm(false);
      load();
    } finally {
      setSaving(false);
    }
  };

  // ── Ouvrir l'édition ──────────────────────────────────────────────────────
  const startEdit = (p) => {
    setEditId(p.id);
    setEditForm({
      titre: p.titre || '',
      description: p.description || '',
      competences_requises: p.competences_requises || '',
    });
  };

  const cancelEdit = () => { setEditId(null); setEditForm(EMPTY); };

  // ── Sauvegarder l'édition ─────────────────────────────────────────────────
  const handleUpdate = async () => {
    if (!editForm.titre.trim() || !editForm.description.trim()) return;
    setEditSaving(true);
    try {
      await updatePoste(editId, editForm);
      setEditId(null);
      setEditForm(EMPTY);
      load();
    } finally {
      setEditSaving(false);
    }
  };

  // ── Supprimer un poste ────────────────────────────────────────────────────
  const handleDelete = async (id) => {
    setDeletingId(id);
    try {
      await deletePoste(id);
      setConfirmDelete(null);
      load();
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <>
      {/* Header */}
      <div className="page-header">
        <span className="page-header-title">Postes</span>
        <div className="page-header-right">
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {postes.length} poste{postes.length !== 1 ? 's' : ''}
          </span>
          <button className="btn btn-primary btn-sm" onClick={() => setShowForm(v => !v)}>
            {showForm ? '✕ Annuler' : '+ Nouveau poste'}
          </button>
        </div>
      </div>

      <div className="page-content">

        {/* Formulaire de création */}
        {showForm && (
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">
              <span className="card-title">Nouveau poste</span>
            </div>
            <div className="card-body">
              {FIELDS.map(f => (
                <div className="form-group" key={f.key}>
                  <label className="form-label">{f.label}</label>
                  <textarea
                    className="form-textarea"
                    rows={f.rows}
                    value={form[f.key]}
                    onChange={e => setForm({ ...form, [f.key]: e.target.value })}
                  />
                </div>
              ))}
              <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
                <button
                  className="btn btn-primary"
                  onClick={handleSubmit}
                  disabled={saving || !form.titre.trim() || !form.description.trim()}
                >
                  {saving ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Création…</> : 'Créer le poste'}
                </button>
                <button className="btn btn-ghost" onClick={() => { setForm(EMPTY); setShowForm(false); }}>
                  Annuler
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Modal de confirmation de suppression */}
        {confirmDelete && (
          <div style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
            zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <div className="card" style={{ maxWidth: 420, width: '90%', margin: 0 }}>
              <div className="card-header">
                <span className="card-title" style={{ color: '#dc2626' }}>🗑 Supprimer le poste</span>
              </div>
              <div className="card-body">
                <p style={{ marginBottom: 16, color: 'var(--text-muted)' }}>
                  Êtes-vous sûr de vouloir supprimer le poste{' '}
                  <strong style={{ color: 'var(--text)' }}>« {confirmDelete.titre} »</strong> ?
                  <br />
                  <span style={{ fontSize: '0.82rem', color: '#dc2626' }}>
                    Cette action est irréversible et supprimera toutes les candidatures associées.
                  </span>
                </p>
                <div style={{ display: 'flex', gap: 10 }}>
                  <button
                    className="btn"
                    style={{ background: '#dc2626', color: '#fff', border: 'none' }}
                    onClick={() => handleDelete(confirmDelete.id)}
                    disabled={deletingId === confirmDelete.id}
                  >
                    {deletingId === confirmDelete.id
                      ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Suppression…</>
                      : 'Confirmer la suppression'}
                  </button>
                  <button className="btn btn-ghost" onClick={() => setConfirmDelete(null)}>
                    Annuler
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Liste des postes */}
        {loading ? (
          <div className="empty-state">
            <div className="spinner" style={{ margin: '0 auto 12px' }} />
            Chargement…
          </div>
        ) : postes.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {postes.map(p => (
              <div key={p.id} className="card" style={{ borderLeft: '4px solid var(--red)' }}>
                {editId === p.id ? (
                  /* ── Mode édition ── */
                  <div className="card-body" style={{ padding: '16px 20px' }}>
                    <div style={{ fontWeight: 700, marginBottom: 12, fontSize: '0.9rem' }}>
                      ✏️ Modifier le poste
                    </div>
                    {FIELDS.map(f => (
                      <div className="form-group" key={f.key}>
                        <label className="form-label">{f.label}</label>
                        <textarea
                          className="form-textarea"
                          rows={f.rows}
                          value={editForm[f.key]}
                          onChange={e => setEditForm({ ...editForm, [f.key]: e.target.value })}
                        />
                      </div>
                    ))}
                    <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
                      <button
                        className="btn btn-primary"
                        onClick={handleUpdate}
                        disabled={editSaving || !editForm.titre.trim() || !editForm.description.trim()}
                      >
                        {editSaving
                          ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Sauvegarde…</>
                          : '✓ Sauvegarder'}
                      </button>
                      <button className="btn btn-ghost" onClick={cancelEdit}>Annuler</button>
                    </div>
                  </div>
                ) : (
                  /* ── Mode affichage ── */
                  <div className="card-body" style={{ padding: '16px 20px' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                      <div style={{
                        width: 40, height: 40, borderRadius: 8, flexShrink: 0,
                        background: 'var(--red-light)', border: '1.5px solid var(--red-mid)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 18,
                      }}>
                        💼
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 700, fontSize: '0.975rem', marginBottom: 4 }}>
                          {p.titre}
                        </div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 8 }}>
                          {p.description}
                        </div>
                        {p.competences_requises && (
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                            {p.competences_requises.split(',').map(k => k.trim()).filter(Boolean).map(k => (
                              <span key={k} className="badge badge-gray">{k}</span>
                            ))}
                          </div>
                        )}
                      </div>
                      {/* Actions */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                        <span style={{ fontSize: '0.75rem', color: 'var(--gray-400)', marginRight: 4 }}>
                          #{p.id}
                        </span>
                        <button
                          className="btn btn-sm"
                          title="Modifier ce poste"
                          onClick={() => startEdit(p)}
                          style={{
                            background: 'var(--surface)',
                            border: '1.5px solid var(--border)',
                            color: 'var(--text)',
                            padding: '5px 10px',
                            fontSize: '0.78rem',
                            display: 'flex', alignItems: 'center', gap: 4,
                          }}
                        >
                          ✏️ Modifier
                        </button>
                        <button
                          className="btn btn-sm"
                          title="Supprimer ce poste"
                          onClick={() => setConfirmDelete(p)}
                          style={{
                            background: '#fff0f0',
                            border: '1.5px solid #fca5a5',
                            color: '#dc2626',
                            padding: '5px 10px',
                            fontSize: '0.78rem',
                            display: 'flex', alignItems: 'center', gap: 4,
                          }}
                        >
                          🗑 Supprimer
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="card">
            <div className="empty-state card-body" style={{ padding: '4rem' }}>
              <div className="empty-state-icon">💼</div>
              <div className="empty-state-title">Aucun poste créé</div>
              <div style={{ fontSize: '0.875rem', marginBottom: 16 }}>
                Créez des postes pour organiser automatiquement les CVs reçus.
              </div>
              <button className="btn btn-primary" onClick={() => setShowForm(true)}>
                + Créer le premier poste
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
