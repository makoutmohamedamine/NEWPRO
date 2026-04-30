import { useEffect, useMemo, useState } from 'react';
import { getDomains, getDomainCandidates } from '../api/api';

function resolveCvUrl(url) {
  if (!url) return '';
  const full = url.startsWith('http://') || url.startsWith('https://') ? url : `http://127.0.0.1:8000${url}`;
  return encodeURI(full);
}

function CvCard({ candidate }) {
  const url = resolveCvUrl(candidate.cvUrl);
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
        <button
          className="btn btn-outline"
          type="button"
          disabled={!url}
          style={{ pointerEvents: url ? 'auto' : 'none', opacity: url ? 1 : 0.5 }}
          onClick={() => url && window.open(url, '_blank', 'noopener')}
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
  const [query, setQuery] = useState('');

  useEffect(() => {
    setLoading(true);
    getDomains()
      .then((res) => {
        const list = res.data.domains || [];
        setDomains(list);
        if (list.length > 0) {
          setActiveDomainId(list[0].id);
        }
      })
      .catch((err) => setError(err?.response?.data?.error || 'Impossible de charger les domaines.'))
      .finally(() => setLoading(false));
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

  return (
    <>
      <div className="page-header">
        <span className="page-header-title">Dossiers CV par domaine</span>
        <div className="page-header-right">
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
                      <CvCard key={candidate.id} candidate={candidate} />
                    ))}
                  </div>
                )}
              </div>
            </section>
          </div>
        )}
      </div>
    </>
  );
}

