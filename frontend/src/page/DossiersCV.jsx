import { useEffect, useMemo, useState } from 'react';
import mammoth from 'mammoth';
import { createDomain, getDomains, getDomainCandidates, moveCandidateDomain } from '../api/api';

function resolveCvUrl(url) {
  if (!url) return '';
  const full = url.startsWith('http://') || url.startsWith('https://') ? url : `http://127.0.0.1:8000${url}`;
  return encodeURI(full);
}

function CvCard({ candidate, domains, onMoveDomain, movingId, onPreviewCv }) {
  const url = resolveCvUrl(candidate.cvUrl);
  const candidateId = candidate.candidateId || candidate.id;
  const isMoving = movingId === candidateId;
  const [targetDomainId, setTargetDomainId] = useState('');
  return (
    <article className="folder-candidate-card">
      <div className="folder-candidate-top">
        <div>
          <div className="folder-candidate-name">{candidate.fullName || 'Candidat'}</div>
          <div className="folder-candidate-meta">
            {candidate.email || 'Email non renseigne'}
            {candidate.currentTitle ? ` • ${candidate.currentTitle}` : ''}
          </div>
        </div>
        <strong>{Number(candidate.matchScore || 0).toFixed(1)}%</strong>
      </div>
      <div className="folder-candidate-tags">
        <span className="badge badge-gray">{candidate.recommendation || 'A evaluer'}</span>
      </div>
      <div className="folder-candidate-summary">
        {candidate.summary || 'Resume indisponible.'}
      </div>
      <div className="candidate-card-actions" style={{ marginTop: 8 }}>
        <select
          className="form-select"
          style={{ minWidth: 190 }}
          value={targetDomainId}
          disabled={isMoving}
          onChange={(event) => setTargetDomainId(event.target.value)}
        >
          <option value="">
            Changer de dossier
          </option>
          {domains.map((domain) => (
            <option key={domain.id} value={domain.id}>
              {domain.nom}
            </option>
          ))}
        </select>
        <button
          className="btn btn-primary"
          type="button"
          disabled={isMoving || !targetDomainId || Number(targetDomainId) === Number(candidate.domainId)}
          onClick={() => onMoveDomain(candidateId, targetDomainId)}
        >
          {isMoving ? 'Deplacement...' : 'Deplacer'}
        </button>
        <button
          className="btn btn-outline"
          type="button"
          disabled={!url}
          style={{ pointerEvents: url ? 'auto' : 'none', opacity: url ? 1 : 0.5 }}
          onClick={() => url && onPreviewCv(candidate)}
        >
          Ouvrir le CV (PDF/DOCX)
        </button>
      </div>
    </article>
  );
}

export default function DossiersCV() {
  const [domains, setDomains] = useState([]);
  const [activeDomainId, setActiveDomainId] = useState(null);
  const [domainCandidates, setDomainCandidates] = useState({});
  const [loading, setLoading] = useState(true);
  const [loadingDomain, setLoadingDomain] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [query, setQuery] = useState('');
  const [movingId, setMovingId] = useState(null);
  const [creatingDomain, setCreatingDomain] = useState(false);
  const [previewCv, setPreviewCv] = useState(null);
  const [docxHtml, setDocxHtml] = useState('');
  const [docxLoading, setDocxLoading] = useState(false);
  const [docxError, setDocxError] = useState('');

  const loadDomains = () => {
    setLoading(true);
    return getDomains()
      .then((res) => {
        const list = res.data.domains || [];
        setDomains(list);
        if (list.length > 0) {
          setActiveDomainId((current) => current || list[0].id);
        }
      })
      .catch((err) => setError(err?.response?.data?.error || 'Impossible de charger les domaines.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadDomains();
  }, []);

  useEffect(() => {
    if (!activeDomainId || domainCandidates[activeDomainId]) return;
    setLoadingDomain(true);
    getDomainCandidates(activeDomainId)
      .then((res) => {
        setDomainCandidates((current) => ({
          ...current,
          [activeDomainId]: res.data.candidates || [],
        }));
      })
      .catch(() => {})
      .finally(() => setLoadingDomain(false));
  }, [activeDomainId, domainCandidates]);

  const activeCandidates = useMemo(() => {
    const list = domainCandidates[activeDomainId] || [];
    if (!query.trim()) return list;
    return list.filter((c) =>
      [c.fullName, c.email, c.currentTitle, c.targetJob]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(query.toLowerCase()))
    );
  }, [domainCandidates, activeDomainId, query]);

  const totalCvs = Object.values(domainCandidates).reduce((sum, list) => sum + (list?.length || 0), 0);

  const handleMoveDomain = async (candidateId, nextDomainId) => {
    if (!candidateId || !nextDomainId) return;
    setMovingId(candidateId);
    setError('');
    setSuccess('');
    try {
      await moveCandidateDomain(candidateId, nextDomainId);
      setDomainCandidates({});
      setActiveDomainId(Number(nextDomainId));
      await loadDomains();
      setSuccess('Candidat deplace avec succes.');
    } catch (err) {
      setError(err?.response?.data?.error || err?.response?.data?.detail || 'Impossible de deplacer ce candidat.');
    } finally {
      setMovingId(null);
    }
  };

  const handleCreateDomain = async () => {
    const nom = window.prompt('Nom du nouveau dossier (domaine) ?');
    if (!nom || !nom.trim()) return;
    setCreatingDomain(true);
    setError('');
    setSuccess('');
    try {
      await createDomain({ nom: nom.trim() });
      setDomainCandidates({});
      await loadDomains();
      setSuccess('Dossier cree avec succes.');
    } catch (err) {
      setError(err?.response?.data?.error || err?.response?.data?.detail || 'Impossible de creer le dossier.');
    } finally {
      setCreatingDomain(false);
    }
  };

  const getCvType = (candidate) => {
    const name = (candidate?.cvFileName || candidate?.cvUrl || '').toLowerCase();
    if (name.endsWith('.pdf')) return 'pdf';
    if (name.endsWith('.docx')) return 'docx';
    return 'unknown';
  };

  const handlePreviewCv = async (candidate) => {
    const url = resolveCvUrl(candidate?.cvUrl);
    if (!url) return;

    const fileType = getCvType(candidate);
    setPreviewCv({
      url,
      fileName: candidate?.cvFileName || `${candidate?.fullName || 'CV'}`,
      fileType,
    });
    setDocxHtml('');
    setDocxError('');

    if (fileType !== 'docx') return;

    setDocxLoading(true);
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const arrayBuffer = await response.arrayBuffer();
      const result = await mammoth.convertToHtml({ arrayBuffer });
      setDocxHtml(result.value || '<p>Document vide.</p>');
    } catch (err) {
      setDocxError(`Apercu DOCX indisponible (${err?.message || 'erreur'}).`);
    } finally {
      setDocxLoading(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <span className="page-header-title">Dossiers CV par domaine</span>
        <div className="page-header-right">
          <button className="btn btn-primary" type="button" onClick={handleCreateDomain} disabled={creatingDomain}>
            {creatingDomain ? 'Creation...' : 'Creer un dossier'}
          </button>
          <input
            className="form-input"
            style={{ width: 260 }}
            placeholder="Rechercher un candidat dans le domaine..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
      </div>

      <div className="page-content">
        {success && <div className="alert alert-success" style={{ marginBottom: 12 }}>{success}</div>}
        {!loading && !error && (
          <div className="candidate-toolbar-summary">
            <div className="candidate-toolbar-stat">
              <strong>{domains.length}</strong>
              <span>Domaines Colorado</span>
            </div>
            <div className="candidate-toolbar-stat">
              <strong>{totalCvs}</strong>
              <span>CV indexes par l'IA</span>
            </div>
            <div className="candidate-toolbar-stat">
              <strong>{activeCandidates.length}</strong>
              <span>CV dans le domaine selectionne</span>
            </div>
          </div>
        )}

        {loading ? (
          <div className="empty-state">
            <div className="spinner" style={{ margin: '0 auto 12px' }} />
            Chargement des domaines...
          </div>
        ) : error ? (
          <div className="alert alert-error">{error}</div>
        ) : domains.length === 0 ? (
          <div className="workflow-empty">
            <div className="workflow-empty-icon">CV</div>
            <div className="workflow-empty-title">Aucun domaine n'est encore disponible</div>
            <div className="workflow-empty-copy">
              Importez des CV depuis le tableau de bord pour alimenter automatiquement les dossiers par domaine.
            </div>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 18, alignItems: 'flex-start' }}>
            <aside className="card card-body">
              <div className="card-title" style={{ marginBottom: 10 }}>
                Domaines de recrutement
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {domains.map((domain) => {
                  const active = domain.id === activeDomainId;
                  return (
                    <button
                      key={domain.id}
                      type="button"
                      onClick={() => setActiveDomainId(domain.id)}
                      className={`sidebar-link${active ? ' active' : ''}`}
                      style={{
                        justifyContent: 'space-between',
                        borderRadius: 8,
                        border: '1px solid rgba(148,163,184,0.35)',
                        background: active ? 'linear-gradient(90deg,#991b1b,#111827)' : '#020617',
                        color: '#e5e7eb',
                      }}
                    >
                      <span>{domain.nom}</span>
                      <span className="badge badge-black">{domain.candidats_count}</span>
                    </button>
                  );
                })}
              </div>
            </aside>

            <section>
              <div className="card card-body" style={{ marginBottom: 16 }}>
                <div className="card-header" style={{ padding: 0, marginBottom: 10 }}>
                  <span className="card-title">
                    {domains.find((d) => d.id === activeDomainId)?.nom || 'Aucun domaine selectionne'}
                  </span>
                  {loadingDomain && (
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Mise a jour des CV...</span>
                  )}
                </div>
                {activeCandidates.length === 0 ? (
                  <div className="empty-state" style={{ padding: '18px 10px' }}>
                    Aucun CV ne correspond encore a ce domaine.
                  </div>
                ) : (
                  <div className="candidate-grid">
                    {activeCandidates.map((candidate) => (
                      <CvCard
                        key={candidate.id}
                        candidate={candidate}
                        domains={domains}
                        onMoveDomain={handleMoveDomain}
                        movingId={movingId}
                        onPreviewCv={handlePreviewCv}
                      />
                    ))}
                  </div>
                )}
              </div>
            </section>
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
            {previewCv.fileType === 'pdf' ? (
              <object
                data={previewCv.url}
                type="application/pdf"
                style={{ width: '100%', height: 'calc(88vh - 52px)' }}
              >
                <div style={{ padding: 18 }}>
                  Apercu PDF indisponible dans le navigateur.
                </div>
              </object>
            ) : previewCv.fileType === 'docx' ? (
              <div style={{ height: 'calc(88vh - 52px)', overflow: 'auto', padding: 18 }}>
                {docxLoading ? (
                  <div className="empty-state">
                    <div className="spinner" style={{ margin: '0 auto 12px' }} />
                    Chargement du DOCX...
                  </div>
                ) : docxError ? (
                  <div className="alert alert-error">{docxError}</div>
                ) : (
                  <div dangerouslySetInnerHTML={{ __html: docxHtml }} />
                )}
              </div>
            ) : (
              <div style={{ padding: 18 }}>
                Format non supporte pour l apercu integre.
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

