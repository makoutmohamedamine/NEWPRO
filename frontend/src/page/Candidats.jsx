import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  createEntretien,
  deleteCandidate,
  getCandidats,
  getEntretiens,
  getWorkflowStatuses,
  updateCandidate,
} from '../api/api';

const DEFAULT_STATUS_OPTIONS = [
  { value: 'nouveau', label: 'Nouveau', color: '#b42318' },
  { value: 'prequalifie', label: 'Pre-qualifie', color: '#ea580c' },
  { value: 'shortlist', label: 'Shortlist', color: '#0f766e' },
  { value: 'entretien_rh', label: 'Entretien RH', color: '#1d4ed8' },
  { value: 'entretien_technique', label: 'Entretien Technique', color: '#4f46e5' },
  { value: 'validation_manager', label: 'Validation Manager', color: '#7c3aed' },
  { value: 'accepte', label: 'Accepte', color: '#15803d' },
  { value: 'refuse', label: 'Refuse', color: '#6b7280' },
];

const ENTRETIEN_TYPE_OPTIONS = [
  { value: 'rh', label: 'Entretien RH' },
  { value: 'technique', label: 'Entretien technique' },
  { value: 'final', label: 'Entretien final' },
  { value: 'autre', label: 'Autre' },
];

function isInterviewStatus(status) {
  return status === 'entretien_rh' || status === 'entretien_technique' || status === 'entretien';
}

function defaultEntretienTypeFromStatus(status) {
  if (status === 'entretien_technique') return 'technique';
  if (status === 'entretien_rh' || status === 'entretien') return 'rh';
  return 'rh';
}

function pad2(n) {
  return String(n).padStart(2, '0');
}

function toDatetimeLocalValue(d) {
  if (!(d instanceof Date) || Number.isNaN(d.getTime())) return '';
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

function fromDatetimeLocalValue(s) {
  if (!s) return null;
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

function CalendarPlanIcon() {
  return (
    <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>
  );
}

function PlanInterviewModal({ candidate, onClose, onSaved }) {
  const start = new Date();
  const end = new Date(start.getTime() + 60 * 60 * 1000);
  const [form, setForm] = useState({
    titre: `Entretien — ${candidate.fullName || ''}`.trim(),
    type_entretien: defaultEntretienTypeFromStatus(candidate.status),
    debut: toDatetimeLocalValue(start),
    fin: toDatetimeLocalValue(end),
    lieu: '',
    notes: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const candidatureId = candidate.candidatureId;
  const handleSubmit = async (ev) => {
    ev.preventDefault();
    if (!candidatureId) {
      setError('Aucune candidature liée : impossible de planifier un entretien.');
      return;
    }
    const debutIso = fromDatetimeLocalValue(form.debut);
    const finIso = fromDatetimeLocalValue(form.fin);
    if (!debutIso || !finIso) {
      setError('Indiquez une date et heure de début et de fin.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await createEntretien({
        candidature: candidatureId,
        titre: form.titre,
        type_entretien: form.type_entretien,
        debut: debutIso,
        fin: finIso,
        lieu: form.lieu,
        notes: form.notes,
      });
      onSaved();
      onClose();
    } catch (e) {
      const msg = e.response?.data;
      if (typeof msg === 'object' && msg !== null) {
        const parts = Object.entries(msg).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`);
        setError(parts.join(' — ') || 'Erreur de sauvegarde.');
      } else {
        setError(e.message || 'Erreur de sauvegarde.');
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="entretiens-modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="entretiens-modal card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="plan-entretien-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="plan-entretien-title" className="entretiens-modal-title">
          Planifier un entretien
        </h2>
        <p className="candidate-plan-modal-meta">
          {candidate.fullName}
          {candidate.targetJob ? ` — ${candidate.targetJob}` : ''}
        </p>
        {error && <div className="alert alert-error entretiens-modal-error">{error}</div>}
        <form onSubmit={handleSubmit} className="entretiens-form">
          <div className="form-group">
            <label className="form-label" htmlFor="plan-titre">
              Titre
            </label>
            <input
              id="plan-titre"
              className="form-input"
              value={form.titre}
              onChange={(e) => setForm({ ...form, titre: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="plan-type">
              Type
            </label>
            <select
              id="plan-type"
              className="form-select"
              value={form.type_entretien}
              onChange={(e) => setForm({ ...form, type_entretien: e.target.value })}
            >
              {ENTRETIEN_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div className="entretiens-form-row">
            <div className="form-group">
              <label className="form-label" htmlFor="plan-debut">
                Début
              </label>
              <input
                id="plan-debut"
                className="form-input"
                type="datetime-local"
                required
                value={form.debut}
                onChange={(e) => setForm({ ...form, debut: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="plan-fin">
                Fin
              </label>
              <input
                id="plan-fin"
                className="form-input"
                type="datetime-local"
                required
                value={form.fin}
                onChange={(e) => setForm({ ...form, fin: e.target.value })}
              />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="plan-lieu">
              Lieu / lien visio
            </label>
            <input
              id="plan-lieu"
              className="form-input"
              value={form.lieu}
              onChange={(e) => setForm({ ...form, lieu: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="plan-notes">
              Notes
            </label>
            <textarea
              id="plan-notes"
              className="form-textarea"
              rows={2}
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </div>
          <div className="entretiens-form-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Annuler
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving || !candidatureId}>
              {saving ? 'Enregistrement…' : 'Créer dans le calendrier'}
            </button>
          </div>
        </form>
        <p className="candidate-plan-modal-foot">
          L&apos;entretien sera visible tout de suite dans{' '}
          <Link to="/entretiens" onClick={onClose}>
            Entretiens
          </Link>
          .
        </p>
      </div>
    </div>
  );
}

function CandidateCard({ candidate, statusOptions, onStatusChange, onPreviewCv, onDelete, hasEntretienPlanned, onPlanInterview }) {
  const [saving, setSaving] = useState(false);
  const hasEvaluation = Boolean(candidate.targetJob) && Number(candidate.matchScore || 0) > 0;
  const currentStatus = statusOptions.find((item) => item.value === candidate.status);
  const statusColor = currentStatus?.color || '#6b7280';

  const handleStatusChange = async (event) => {
    setSaving(true);
    try {
      await onStatusChange(candidate.candidateId || candidate.id, event.target.value);
    } finally {
      setSaving(false);
    }
  };

  return (
    <article className="candidate-card">
      <div className="candidate-card-top">
        <div className="candidate-card-headcopy">
          <div className="candidate-card-name">{candidate.fullName}</div>
          <div className="candidate-card-meta">
            {candidate.domainName ? `${candidate.domainName} - ${candidate.currentTitle || 'Profil'}` : (candidate.currentTitle || 'Profil non detecte')}
            {' • '}
            {candidate.targetJob || 'Sans poste cible'}
          </div>
        </div>
        {hasEvaluation ? (
          <div className="candidate-score-stack">
            <div className="candidate-score-value">{Number(candidate.matchScore || 0).toFixed(1)}%</div>
            <div className="candidate-score-label">{candidate.recommendation}</div>
          </div>
        ) : (
          <div className="candidate-score-stack candidate-score-stack-muted">
            <div className="candidate-score-empty">Sans score</div>
          </div>
        )}
      </div>

      <div className="candidate-summary-block">
        <div className="candidate-section-title">Resume</div>
        <p className="candidate-summary">{candidate.summary || 'Resume indisponible.'}</p>
      </div>

      <div className="candidate-section-title">Competences</div>
      <div className="candidate-chip-row">
        {(candidate.skills || []).slice(0, 6).map((skill) => (
          <span className="badge badge-gray" key={skill}>{skill}</span>
        ))}
        {(!candidate.skills || candidate.skills.length === 0) && (
          <span className="candidate-empty-text">Aucune competence extraite</span>
        )}
      </div>

      <div className="candidate-detail-grid">
        <div className="candidate-detail-card candidate-detail-card-wide">
          <span className="candidate-detail-label">Contact</span>
          <strong className="candidate-detail-value break-anywhere">{candidate.email || 'N/A'}</strong>
          <small>{candidate.phone || 'Telephone non renseigne'}</small>
        </div>
        <div className="candidate-detail-card">
          <span className="candidate-detail-label">Experience</span>
          <strong className="candidate-detail-value">{candidate.yearsExperience || 0} an(s)</strong>
          <small>{candidate.educationLevel || 'Non precise'}</small>
        </div>
        <div className="candidate-detail-card">
          <span className="candidate-detail-label">Workflow</span>
          <strong className="candidate-detail-value">{candidate.workflowStep}</strong>
          <small>
            <span
              className="badge"
              style={{ background: `${statusColor}18`, color: statusColor, border: `1px solid ${statusColor}44` }}
            >
              {candidate.statusLabel}
            </span>
          </small>
        </div>
      </div>

      {isInterviewStatus(candidate.status) && (
        <div className="candidate-plan-row">
          {candidate.candidatureId ? (
            <>
              <button
                type="button"
                className="candidate-plan-btn"
                onClick={() => onPlanInterview(candidate)}
                title="Planifier un créneau d'entretien"
              >
                <span className="candidate-plan-btn-icon" aria-hidden>
                  <CalendarPlanIcon />
                </span>
                <span className="candidate-plan-btn-text">Planifier</span>
              </button>
              {hasEntretienPlanned && (
                <span className="candidate-plan-badge">
                  Créneau enregistré — voir <Link to="/entretiens">Entretiens</Link>
                </span>
              )}
            </>
          ) : (
            <span className="candidate-plan-unavailable">
              Statut entretien : associez d&apos;abord ce candidat à une fiche de poste pour activer la planification.
            </span>
          )}
        </div>
      )}

      <div className="candidate-card-actions">
        <div className="candidate-action-field">
          <label className="candidate-action-label">Changer le statut</label>
          <select className="form-select" value={candidate.status} onChange={handleStatusChange} disabled={saving}>
            {statusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <button
          className="btn btn-outline"
          type="button"
          onClick={() => candidate.cvUrl && onPreviewCv(candidate)}
          style={{ pointerEvents: candidate.cvUrl ? 'auto' : 'none', opacity: candidate.cvUrl ? 1 : 0.5 }}
        >
          Ouvrir le CV
        </button>
        <button
          className="btn btn-ghost"
          type="button"
          onClick={() => onDelete(candidate)}
        >
          Supprimer
        </button>
      </div>
    </article>
  );
}

export default function Candidats() {
  const [items, setItems] = useState([]);
  const [entretiens, setEntretiens] = useState([]);
  const [statusOptions, setStatusOptions] = useState(DEFAULT_STATUS_OPTIONS);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [previewCv, setPreviewCv] = useState(null);
  const [planForCandidate, setPlanForCandidate] = useState(null);

  const candidatureIdsWithEntretien = useMemo(() => {
    const ids = new Set();
    for (const e of entretiens) {
      const id = e.candidature;
      if (id != null) ids.add(Number(id));
    }
    return ids;
  }, [entretiens]);

  const load = () => {
    setLoading(true);
    Promise.all([getCandidats(), getEntretiens()])
      .then(([cRes, eRes]) => {
        setItems(cRes.data.candidates || []);
        const ent = Array.isArray(eRes.data) ? eRes.data : eRes.data?.results || [];
        setEntretiens(ent);
      })
      .finally(() => setLoading(false));
  };

  const refreshEntretiensOnly = () => {
    getEntretiens()
      .then((eRes) => {
        const ent = Array.isArray(eRes.data) ? eRes.data : eRes.data?.results || [];
        setEntretiens(ent);
      })
      .catch(() => {});
  };

  useEffect(() => {
    load();
    getWorkflowStatuses()
      .then((res) => setStatusOptions(res.data?.statuses?.length ? res.data.statuses : DEFAULT_STATUS_OPTIONS))
      .catch(() => setStatusOptions(DEFAULT_STATUS_OPTIONS));
  }, []);

  const filtered = useMemo(() => {
    return items.filter((item) => {
      const matchesQuery = [item.fullName, item.email, item.targetJob, item.currentTitle]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(query.toLowerCase()));
      const matchesStatus = status === 'all' ? true : item.status === status;
      return matchesQuery && matchesStatus;
    });
  }, [items, query, status]);

  const handleStatusChange = async (candidateId, nextStatus) => {
    const res = await updateCandidate(candidateId, { status: nextStatus });
    const updated = res.data.candidate;
    setItems((current) =>
      current.map((item) => ((item.candidateId || item.id) === candidateId ? updated : item))
    );
    if (isInterviewStatus(nextStatus)) {
      refreshEntretiensOnly();
    }
  };

  const hasEntretienForCandidate = (c) => {
    const cid = c.candidatureId != null ? Number(c.candidatureId) : null;
    if (cid == null) return false;
    return candidatureIdsWithEntretien.has(cid);
  };

  const resolveCvUrl = (url) => {
    if (!url) return '';
    const full = url.startsWith('http://') || url.startsWith('https://')
      ? url
      : `http://127.0.0.1:8000${url}`;
    return encodeURI(full);
  };

  const handlePreviewCv = (candidate) => {
    setPreviewCv({
      fileName: candidate.cvFileName || `${candidate.fullName || 'CV'}.pdf`,
      url: resolveCvUrl(candidate.cvUrl),
    });
  };

  const handleDeleteCandidate = async (candidate) => {
    const candidateId = candidate.candidateId || candidate.id;
    if (!candidateId) return;
    const ok = window.confirm(`Supprimer le candidat ${candidate.fullName || ''} ?`);
    if (!ok) return;
    await deleteCandidate(candidateId);
    setItems((current) => current.filter((item) => (item.candidateId || item.id) !== candidateId));
  };

  return (
    <>
      <div className="page-header">
        <span className="page-header-title">Candidats</span>
        <div className="page-header-right">
          <input
            className="form-input"
            style={{ width: 240 }}
            placeholder="Rechercher un candidat..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <select className="form-select" style={{ width: 180 }} value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="all">Tous les statuts</option>
            {statusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="page-content">
        {!loading && (
          <div className="candidate-toolbar-summary">
            <div className="candidate-toolbar-stat">
              <strong>{items.length}</strong>
              <span>Candidats total</span>
            </div>
            <div className="candidate-toolbar-stat">
              <strong>{filtered.length}</strong>
              <span>Affiches</span>
            </div>
          </div>
        )}

        {loading ? (
          <div className="empty-state">
            <div className="spinner" style={{ margin: '0 auto 12px' }} />
            Chargement des candidats...
          </div>
        ) : filtered.length > 0 ? (
          <div className="candidate-grid">
            {filtered.map((candidate) => (
              <CandidateCard
                key={candidate.candidateId ?? candidate.id}
                candidate={candidate}
                statusOptions={statusOptions}
                onStatusChange={handleStatusChange}
                onPreviewCv={handlePreviewCv}
                onDelete={handleDeleteCandidate}
                hasEntretienPlanned={hasEntretienForCandidate(candidate)}
                onPlanInterview={(c) => setPlanForCandidate(c)}
              />
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <div className="empty-state-title">Aucun candidat sur ce filtre</div>
            <div style={{ fontSize: '0.9rem' }}>Ajustez la recherche ou importez de nouveaux CV depuis le dashboard.</div>
          </div>
        )}
      </div>
      {planForCandidate && (
        <PlanInterviewModal
          key={planForCandidate.candidatureId || planForCandidate.candidateId || planForCandidate.id}
          candidate={planForCandidate}
          onClose={() => setPlanForCandidate(null)}
          onSaved={refreshEntretiensOnly}
        />
      )}

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
