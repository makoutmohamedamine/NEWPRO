import { useEffect, useMemo, useState } from 'react';
import { deleteCandidate, getCandidats, getWorkflowStatuses, updateCandidate } from '../api/api';

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

function CandidateCard({ candidate, statusOptions, onStatusChange, onPreviewCv, onDelete }) {
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
  const [statusOptions, setStatusOptions] = useState(DEFAULT_STATUS_OPTIONS);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [previewCv, setPreviewCv] = useState(null);

  const load = () => {
    setLoading(true);
    getCandidats()
      .then((res) => setItems(res.data.candidates || []))
      .finally(() => setLoading(false));
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
                key={candidate.id}
                candidate={candidate}
                statusOptions={statusOptions}
                onStatusChange={handleStatusChange}
                onPreviewCv={handlePreviewCv}
                onDelete={handleDeleteCandidate}
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
