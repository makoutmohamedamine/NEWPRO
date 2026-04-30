import { useEffect, useMemo, useState } from 'react';
import { createPoste, deleteCandidate, deletePoste, getDossiers, getPostes, updatePoste } from '../api/api';

const EMPTY = {
  titre: '',
  description: '',
  competences_requises: '',
  competences_optionnelles: '',
  langues_requises: '',
  departement: '',
  localisation: '',
  type_contrat: '',
  experience_min_annees: 0,
  niveau_etudes_requis: '',
  quota_cible: 1,
  score_qualification: 70,
  niveau_priorite: 'medium',
};

function PosteForm({ value, onChange, onSubmit, onCancel, saving, submitLabel }) {
  return (
    <div className="post-form-grid">
      <div className="form-group">
        <label className="form-label">Titre</label>
        <input className="form-input" value={value.titre} onChange={(e) => onChange({ ...value, titre: e.target.value })} />
      </div>
      <div className="form-group">
        <label className="form-label">Departement</label>
        <input className="form-input" value={value.departement} onChange={(e) => onChange({ ...value, departement: e.target.value })} />
      </div>
      <div className="form-group post-form-span-2">
        <label className="form-label">Description</label>
        <textarea className="form-textarea" rows={4} value={value.description} onChange={(e) => onChange({ ...value, description: e.target.value })} />
      </div>
      <div className="form-group post-form-span-2">
        <label className="form-label">Competences requises</label>
        <textarea
          className="form-textarea"
          rows={3}
          value={value.competences_requises}
          onChange={(e) => onChange({ ...value, competences_requises: e.target.value })}
        />
      </div>
      <div className="form-group post-form-span-2">
        <label className="form-label">Competences optionnelles</label>
        <textarea
          className="form-textarea"
          rows={2}
          value={value.competences_optionnelles}
          onChange={(e) => onChange({ ...value, competences_optionnelles: e.target.value })}
        />
      </div>
      <div className="form-group">
        <label className="form-label">Langues</label>
        <input className="form-input" value={value.langues_requises} onChange={(e) => onChange({ ...value, langues_requises: e.target.value })} />
      </div>
      <div className="form-group">
        <label className="form-label">Localisation</label>
        <input className="form-input" value={value.localisation} onChange={(e) => onChange({ ...value, localisation: e.target.value })} />
      </div>
      <div className="form-group">
        <label className="form-label">Type de contrat</label>
        <input className="form-input" value={value.type_contrat} onChange={(e) => onChange({ ...value, type_contrat: e.target.value })} />
      </div>
      <div className="form-group">
        <label className="form-label">Niveau d etudes</label>
        <input className="form-input" value={value.niveau_etudes_requis} onChange={(e) => onChange({ ...value, niveau_etudes_requis: e.target.value })} />
      </div>
      <div className="form-group">
        <label className="form-label">Experience min (ans)</label>
        <input className="form-input" type="number" value={value.experience_min_annees} onChange={(e) => onChange({ ...value, experience_min_annees: Number(e.target.value) })} />
      </div>
      <div className="form-group">
        <label className="form-label">Seuil qualification</label>
        <input className="form-input" type="number" value={value.score_qualification} onChange={(e) => onChange({ ...value, score_qualification: Number(e.target.value) })} />
      </div>
      <div className="form-group">
        <label className="form-label">Quota cible</label>
        <input className="form-input" type="number" value={value.quota_cible} onChange={(e) => onChange({ ...value, quota_cible: Number(e.target.value) })} />
      </div>
      <div className="form-group">
        <label className="form-label">Priorite</label>
        <select className="form-select" value={value.niveau_priorite} onChange={(e) => onChange({ ...value, niveau_priorite: e.target.value })}>
          <option value="low">low</option>
          <option value="medium">medium</option>
          <option value="high">high</option>
          <option value="urgent">urgent</option>
        </select>
      </div>
      <div className="post-form-actions">
        <button className="btn btn-primary" type="button" disabled={saving} onClick={onSubmit}>
          {saving ? 'Enregistrement...' : submitLabel}
        </button>
        <button className="btn btn-ghost" type="button" onClick={onCancel}>Annuler</button>
      </div>
    </div>
  );
}

export default function Postes() {
  const [jobs, setJobs] = useState([]);
  const [folders, setFolders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [editingId, setEditingId] = useState(null);
  const [openCandidatesJobId, setOpenCandidatesJobId] = useState(null);
  const [previewCv, setPreviewCv] = useState(null);

  const load = () => {
    setLoading(true);
    setError('');
    Promise.all([getPostes(), getDossiers()])
      .then(([jobsRes, foldersRes]) => {
        setJobs(jobsRes.data || []);
        setFolders(foldersRes.data?.dossiers || []);
      })
      .catch((err) => {
        setError(err?.response?.data?.error || 'Impossible de charger les postes.');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const candidatesByJobId = useMemo(() => {
    const index = {};
    folders.forEach((folder) => {
      const ranked = [...(folder.cvs || [])].sort(
        (a, b) => Number(b.matchScore || 0) - Number(a.matchScore || 0)
      );
      index[folder.id] = ranked;
    });
    return index;
  }, [folders]);

  const resolveCvUrl = (url) => {
    if (!url) return '';
    const full = url.startsWith('http://') || url.startsWith('https://')
      ? url
      : `http://127.0.0.1:8000${url}`;
    return encodeURI(full);
  };

  const handleCreate = async () => {
    setSaving(true);
    try {
      await createPoste(form);
      setForm(EMPTY);
      setCreating(false);
      load();
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async () => {
    setSaving(true);
    try {
      await updatePoste(editingId, form);
      setEditingId(null);
      setForm(EMPTY);
      load();
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteCandidate = async (candidateId) => {
    if (!candidateId) return;
    const ok = window.confirm('Supprimer ce candidat ?');
    if (!ok) return;
    try {
      await deleteCandidate(candidateId);
      load();
    } catch (err) {
      setError(err?.response?.data?.error || 'Suppression du candidat impossible.');
    }
  };

  return (
    <>
      <div className="page-header">
        <span className="page-header-title">Postes</span>
        <div className="page-header-right">
          <button className="btn btn-primary" onClick={() => { setCreating((open) => !open); setEditingId(null); setForm(EMPTY); }}>
            {creating ? 'Fermer' : 'Nouveau poste'}
          </button>
        </div>
      </div>

      <div className="page-content">
        {creating && (
          <div className="card" style={{ marginBottom: 18 }}>
            <div className="card-header">
              <span className="card-title">Creer une fiche de poste</span>
            </div>
            <div className="card-body">
              <PosteForm
                value={form}
                onChange={setForm}
                onSubmit={handleCreate}
                onCancel={() => { setCreating(false); setForm(EMPTY); }}
                saving={saving}
                submitLabel="Creer le poste"
              />
            </div>
          </div>
        )}

        {loading ? (
          <div className="empty-state">
            <div className="spinner" style={{ margin: '0 auto 12px' }} />
            Chargement des postes...
          </div>
        ) : error ? (
          <div className="alert alert-error">{error}</div>
        ) : (
          <div className="jobs-grid">
            {jobs.map((job) => (
              <div className="card job-card" key={job.id}>
                <div className="card-body">
                  {editingId === job.id ? (
                    <PosteForm
                      value={form}
                      onChange={setForm}
                      onSubmit={handleUpdate}
                      onCancel={() => { setEditingId(null); setForm(EMPTY); }}
                      saving={saving}
                      submitLabel="Sauvegarder"
                    />
                  ) : (
                    <>
                      <div className="job-card-top">
                        <div>
                          <div className="job-card-title">{job.titre}</div>
                          <div className="job-card-meta">
                            {job.departement || 'Sans departement'} • {job.localisation || 'Lieu non defini'}
                          </div>
                        </div>
                        <span className="badge badge-black">{job.niveau_priorite}</span>
                      </div>
                      <p className="job-card-description">{job.description}</p>
                      <div className="candidate-chip-row">
                        {(job.competences_requises || '')
                          .split(',')
                          .map((item) => item.trim())
                          .filter(Boolean)
                          .slice(0, 6)
                          .map((item) => (
                            <span key={item} className="badge badge-gray">{item}</span>
                          ))}
                      </div>
                      <div className="job-card-stats">
                        <div><span>Seuil</span><strong>{job.score_qualification}%</strong></div>
                        <div><span>Experience</span><strong>{job.experience_min_annees} ans</strong></div>
                        <div><span>Quota</span><strong>{job.quota_cible}</strong></div>
                      </div>
                      <div style={{ display: 'flex', gap: 10, marginTop: 18 }}>
                        <button
                          className="btn btn-primary"
                          onClick={() => setOpenCandidatesJobId((prev) => (prev === job.id ? null : job.id))}
                        >
                          {openCandidatesJobId === job.id ? 'Masquer candidats' : 'Voir candidats'}
                        </button>
                        <button
                          className="btn btn-outline"
                          onClick={() => {
                            setEditingId(job.id);
                            setCreating(false);
                            setForm({ ...EMPTY, ...job });
                          }}
                        >
                          Modifier
                        </button>
                        <button
                          className="btn btn-ghost"
                          onClick={() =>
                            deletePoste(job.id)
                              .then(load)
                              .catch((err) =>
                                setError(err?.response?.data?.error || 'Suppression du poste impossible.')
                              )
                          }
                        >
                          Supprimer
                        </button>
                      </div>
                      {openCandidatesJobId === job.id && (
                        <div style={{ marginTop: 14 }}>
                          <div className="form-label" style={{ marginBottom: 8 }}>
                            Candidats disponibles (classes par score)
                          </div>
                          {(candidatesByJobId[job.id] || []).length > 0 ? (
                            <div style={{ display: 'grid', gap: 8 }}>
                              {(candidatesByJobId[job.id] || []).map((candidate, idx) => (
                                <div
                                  key={`${job.id}-${candidate.id}`}
                                  style={{
                                    border: '1px solid #e5e7eb',
                                    borderRadius: 10,
                                    padding: '10px 12px',
                                  }}
                                >
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                                    <strong>{idx + 1}. {candidate.fullName}</strong>
                                    <div style={{ fontWeight: 700 }}>{Number(candidate.matchScore || 0).toFixed(1)}%</div>
                                  </div>
                                  <div style={{ color: '#6b7280', fontSize: 13, marginTop: 6, display: 'grid', gap: 4 }}>
                                    <div>
                                      Email:{' '}
                                      {candidate.email ? (
                                        <a href={`mailto:${candidate.email}`} style={{ color: '#2563eb' }}>
                                          {candidate.email}
                                        </a>
                                      ) : (
                                        'Non renseigne'
                                      )}
                                    </div>
                                    <div>Telephone: {candidate.phone || 'Non renseigne'}</div>
                                    <div>Localisation: {candidate.location || 'Non renseignee'}</div>
                                  </div>
                                  <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                    {candidate.cvUrl ? (
                                      <button
                                        className="btn btn-outline"
                                        type="button"
                                        onClick={() =>
                                          setPreviewCv({
                                            url: resolveCvUrl(candidate.cvUrl),
                                            fileName: candidate.cvFileName || `${candidate.fullName}.pdf`,
                                          })
                                        }
                                      >
                                        Voir CV
                                      </button>
                                    ) : (
                                      <span className="badge badge-gray">CV indisponible</span>
                                    )}
                                    {candidate.cvUrl && (
                                      <a
                                        className="btn btn-ghost"
                                        href={resolveCvUrl(candidate.cvUrl)}
                                        download={candidate.cvFileName || true}
                                      >
                                        Telecharger CV
                                      </a>
                                    )}
                                    <button
                                      className="btn btn-ghost"
                                      type="button"
                                      onClick={() => handleDeleteCandidate(candidate.candidateId || candidate.id)}
                                    >
                                      Supprimer
                                    </button>
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="empty-state" style={{ padding: '10px 8px' }}>
                              Aucun candidat evalue pour ce poste.
                            </div>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      {previewCv && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.55)',
            zIndex: 1200,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 18,
          }}
          onClick={() => setPreviewCv(null)}
        >
          <div
            style={{ width: 'min(1050px, 96vw)', height: '88vh', background: '#fff', borderRadius: 12, overflow: 'hidden' }}
            onClick={(event) => event.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', borderBottom: '1px solid #e5e7eb' }}>
              <strong style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{previewCv.fileName}</strong>
              <button className="btn btn-ghost" type="button" onClick={() => setPreviewCv(null)}>Fermer</button>
            </div>
            <object
              data={previewCv.url}
              type="application/pdf"
              style={{ width: '100%', height: 'calc(88vh - 52px)' }}
            >
              <div style={{ padding: 18 }}>
                Apercu indisponible dans le navigateur.
                <div style={{ marginTop: 10 }}>
                  <a className="btn btn-primary" href={previewCv.url} target="_blank" rel="noreferrer">
                    Ouvrir le CV
                  </a>
                </div>
              </div>
            </object>
          </div>
        </div>
      )}
    </>
  );
}
