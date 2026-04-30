import { useState, useRef } from 'react';
import { analyseCV_IA } from '../api/api';
import { getPostes } from '../api/api';
import { useEffect } from 'react';

// ── Composants utilitaires ────────────────────────────────────────────────────

function ScoreBadge({ score }) {
  const s = Math.round(score || 0);
  const color = s >= 75 ? '#16a34a' : s >= 50 ? '#d97706' : '#dc2626';
  const bg    = s >= 75 ? '#dcfce7' : s >= 50 ? '#fef3c7' : '#fee2e2';
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: 72, height: 72, borderRadius: '50%',
      background: bg, color, fontWeight: 800, fontSize: '1.4rem',
      border: `3px solid ${color}`, flexShrink: 0,
    }}>
      {s}
    </div>
  );
}

function Tag({ label, color = '#3b82f6' }) {
  return (
    <span style={{
      display: 'inline-block', padding: '3px 10px', borderRadius: 20,
      background: color + '20', color, fontSize: '0.75rem', fontWeight: 600,
      margin: '2px 3px',
    }}>
      {label}
    </span>
  );
}

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{
        fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.08em',
        textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 8,
      }}>
        {title}
      </div>
      {children}
    </div>
  );
}

// ── Page principale ───────────────────────────────────────────────────────────

export default function AnalyseIA() {
  const [file, setFile]         = useState(null);
  const [postes, setPostes]     = useState([]);
  const [jobId, setJobId]       = useState('');
  const [loading, setLoading]   = useState(false);
  const [result, setResult]     = useState(null);
  const [error, setError]       = useState('');
  const fileRef = useRef();

  useEffect(() => {
    getPostes().then(r => setPostes(r.data)).catch(() => {});
  }, []);

  const getApiErrorMessage = (err) => {
    const data = err?.response?.data;

    if (typeof data === 'string' && data.trim()) {
      return data.slice(0, 240);
    }

    if (data && typeof data === 'object') {
      if (typeof data.error === 'string' && data.error.trim()) return data.error;
      if (typeof data.detail === 'string' && data.detail.trim()) return data.detail;
      if (Array.isArray(data.non_field_errors) && data.non_field_errors.length > 0) {
        return String(data.non_field_errors[0]);
      }
    }

    if (err?.code === 'ECONNABORTED') {
      return 'Delai depasse. Le serveur a mis trop de temps a repondre.';
    }

    if (err?.response?.status) {
      return `Erreur serveur (${err.response.status}).`;
    }

    if (err?.request) {
      return 'Impossible de joindre le backend. Verifiez que le serveur Django tourne sur http://127.0.0.1:8000.';
    }

    return 'Erreur lors de l\'analyse.';
  };

  const isSupportedFile = (f) => {
    const name = (f?.name || '').toLowerCase();
    return name.endsWith('.pdf') || name.endsWith('.docx');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (!f) return;
    if (!isSupportedFile(f)) {
      setError('Format non supporte. Utilisez un fichier PDF ou DOCX.');
      setFile(null);
      return;
    }
    setError('');
    setFile(f);
  };

  const handleAnalyse = async () => {
    if (!file) { setError('Veuillez sélectionner un fichier CV.'); return; }
    if (!isSupportedFile(file)) { setError('Format non supporte. Utilisez un fichier PDF ou DOCX.'); return; }
    setError('');
    setResult(null);
    setLoading(true);

    try {
      const fd = new FormData();
      fd.append('cv', file);
      const poste = postes.find(p => String(p.id) === String(jobId));
      if (poste) {
        fd.append('job_title', poste.titre || '');
        fd.append('job_desc',  poste.description || '');
      }
      const res = await analyseCV_IA(fd);
      setResult(res.data);
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  const recoBadge = (r) => {
    if (!r) return null;
    const map = {
      'À retenir':   { bg: '#dcfce7', color: '#16a34a' },
      'Intéressant': { bg: '#fef3c7', color: '#d97706' },
      'Insuffisant': { bg: '#fee2e2', color: '#dc2626' },
    };
    const style = map[r] || { bg: '#f3f4f6', color: '#6b7280' };
    return (
      <span style={{
        padding: '4px 14px', borderRadius: 20,
        background: style.bg, color: style.color,
        fontWeight: 700, fontSize: '0.85rem',
      }}>
        {r}
      </span>
    );
  };

  return (
    <>
      <div className="page-header">
        <span className="page-header-title">Analyse IA des CVs</span>
        <div className="page-header-right">
          <span style={{
            fontSize: '0.75rem', padding: '4px 12px', borderRadius: 20,
            background: '#ede9fe', color: '#7c3aed', fontWeight: 600,
          }}>
            
          </span>
        </div>
      </div>

      <div className="page-content" style={{ display: 'grid', gridTemplateColumns: result ? '380px 1fr' : '1fr', gap: 20, alignItems: 'start' }}>

        {/* ── Panneau de saisie ── */}
        <div className="card card-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text)' }}>
            Analyser un CV
          </div>

          {/* Zone de dépôt fichier */}
          <div
            onDrop={handleDrop}
            onDragOver={e => e.preventDefault()}
            onClick={() => fileRef.current?.click()}
            style={{
              border: '2px dashed ' + (file ? '#7c3aed' : 'var(--border)'),
              borderRadius: 10, padding: '24px 16px', textAlign: 'center',
              cursor: 'pointer', background: file ? '#ede9fe20' : 'var(--surface)',
              transition: 'all 0.2s',
            }}
          >
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx"
              style={{ display: 'none' }}
              onChange={e => {
                const selected = e.target.files?.[0];
                if (!selected) return;
                if (!isSupportedFile(selected)) {
                  setError('Format non supporte. Utilisez un fichier PDF ou DOCX.');
                  setFile(null);
                  return;
                }
                setError('');
                setFile(selected);
              }}
            />
            {file ? (
              <>
                <div style={{ fontSize: '2rem', marginBottom: 6 }}>📄</div>
                <div style={{ fontWeight: 600, fontSize: '0.875rem', color: '#7c3aed' }}>{file.name}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>
                  {(file.size / 1024).toFixed(0)} Ko — cliquer pour changer
                </div>
              </>
            ) : (
              <>
                <div style={{ fontSize: '2rem', marginBottom: 6 }}>⬆</div>
                <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>Déposer ou cliquer</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>PDF ou DOCX</div>
              </>
            )}
          </div>

          {/* Poste cible (optionnel) */}
          <div>
            <label style={{ fontSize: '0.8rem', fontWeight: 600, display: 'block', marginBottom: 6 }}>
              Poste cible <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(optionnel)</span>
            </label>
            <select
              className="form-input"
              value={jobId}
              onChange={e => setJobId(e.target.value)}
              style={{ width: '100%' }}
            >
              <option value="">— Analyse générale —</option>
              {postes.map(p => (
                <option key={p.id} value={p.id}>{p.titre}</option>
              ))}
            </select>
          </div>

          {error && (
            <div style={{
              background: '#fee2e2', color: '#dc2626', borderRadius: 8,
              padding: '10px 14px', fontSize: '0.8rem', fontWeight: 600,
            }}>
              {error}
            </div>
          )}

          <button
            className="btn btn-primary"
            style={{ width: '100%', justifyContent: 'center', gap: 8 }}
            disabled={loading || !file}
            onClick={handleAnalyse}
          >
            {loading ? (
              <><span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} /> Analyse en cours…</>
            ) : (
              'Analyser avec l\'IA'
            )}
          </button>

          {!result && !loading && (
            <div style={{
              fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.6,
              background: 'var(--surface)', borderRadius: 8, padding: '10px 12px',
            }}>
              L'IA extrait automatiquement les informations clés, évalue le niveau d'études,
              les compétences, l'expérience et génère un résumé professionnel du candidat.
            </div>
          )}
        </div>

        {/* ── Résultats ── */}
        {result && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* Alerte IA non disponible */}
            {!result.ia_disponible && (
              <div style={{
                background: '#fef3c7', color: '#92400e', borderRadius: 10,
                padding: '12px 16px', fontSize: '0.85rem', fontWeight: 600,
              }}>
                ⚠ {(result.ai_provider || 'IA')} indisponible ({result.groq_error || result.deepseek_error || result.error || 'service non joignable'}). Fallback ML actif.
              </div>
            )}

            {/* En-tête candidat */}
            <div className="card card-body" style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
              <ScoreBadge score={result.score_global} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 800, fontSize: '1.15rem' }}>
                  {[result.prenom, result.nom].filter(Boolean).join(' ') || 'Nom non détecté'}
                </div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: 2 }}>
                  {result.email || ''}{result.email && result.telephone ? ' · ' : ''}{result.telephone || ''}
                </div>
                {result.adresse && (
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{result.adresse}</div>
                )}
                <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  {recoBadge(result.recommandation)}
                  {result.niveau_etudes && (
                    <Tag label={result.niveau_etudes} color="#7c3aed" />
                  )}
                  {result.annees_experience > 0 && (
                    <Tag label={`${result.annees_experience} an${result.annees_experience > 1 ? 's' : ''} d'expérience`} color="#0891b2" />
                  )}
                </div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

              {/* Résumé + Points forts/faibles */}
              <div className="card card-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {result.resume_profil && (
                  <Section title="Résumé du profil">
                    <p style={{ fontSize: '0.875rem', lineHeight: 1.7, color: 'var(--text)', margin: 0 }}>
                      {result.resume_profil}
                    </p>
                  </Section>
                )}

                {result.justification_score && (
                  <Section title="Justification du score">
                    <p style={{ fontSize: '0.82rem', lineHeight: 1.6, color: 'var(--text-muted)', margin: 0 }}>
                      {result.justification_score}
                    </p>
                  </Section>
                )}

                {result.points_forts?.length > 0 && (
                  <Section title="Points forts">
                    <ul style={{ margin: 0, paddingLeft: 16 }}>
                      {result.points_forts.map((p, i) => (
                        <li key={i} style={{ fontSize: '0.82rem', color: '#16a34a', marginBottom: 4 }}>{p}</li>
                      ))}
                    </ul>
                  </Section>
                )}

                {result.points_faibles?.length > 0 && (
                  <Section title="Points à améliorer">
                    <ul style={{ margin: 0, paddingLeft: 16 }}>
                      {result.points_faibles.map((p, i) => (
                        <li key={i} style={{ fontSize: '0.82rem', color: '#dc2626', marginBottom: 4 }}>{p}</li>
                      ))}
                    </ul>
                  </Section>
                )}
              </div>

              {/* Compétences */}
              <div className="card card-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {result.competences_techniques?.length > 0 && (
                  <Section title="Compétences techniques">
                    <div style={{ display: 'flex', flexWrap: 'wrap' }}>
                      {result.competences_techniques.map((c, i) => (
                        <Tag key={i} label={c} color="#7c3aed" />
                      ))}
                    </div>
                  </Section>
                )}

                {result.competences_soft?.length > 0 && (
                  <Section title="Soft skills">
                    <div style={{ display: 'flex', flexWrap: 'wrap' }}>
                      {result.competences_soft.map((c, i) => (
                        <Tag key={i} label={c} color="#0891b2" />
                      ))}
                    </div>
                  </Section>
                )}

                {result.langues?.length > 0 && (
                  <Section title="Langues">
                    <div style={{ display: 'flex', flexWrap: 'wrap' }}>
                      {result.langues.map((l, i) => (
                        <Tag key={i} label={l} color="#059669" />
                      ))}
                    </div>
                  </Section>
                )}
              </div>
            </div>

            {/* Formations & Expériences */}
            {(result.formations?.length > 0 || result.experiences?.length > 0) && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

                {result.formations?.length > 0 && (
                  <div className="card card-body">
                    <Section title="Formations">
                      {result.formations.map((f, i) => (
                        <div key={i} style={{
                          padding: '8px 0', borderBottom: i < result.formations.length - 1 ? '1px solid var(--border)' : 'none',
                        }}>
                          <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{f.diplome}</div>
                          <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                            {f.etablissement}{f.annee ? ` · ${f.annee}` : ''}
                          </div>
                        </div>
                      ))}
                    </Section>
                  </div>
                )}

                {result.experiences?.length > 0 && (
                  <div className="card card-body">
                    <Section title="Expériences">
                      {result.experiences.map((e, i) => (
                        <div key={i} style={{
                          padding: '8px 0', borderBottom: i < result.experiences.length - 1 ? '1px solid var(--border)' : 'none',
                        }}>
                          <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{e.poste}</div>
                          <div style={{ fontSize: '0.78rem', color: '#7c3aed', fontWeight: 600 }}>
                            {e.entreprise}{e.duree ? ` · ${e.duree}` : ''}
                          </div>
                          {e.description && (
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 3 }}>
                              {e.description}
                            </div>
                          )}
                        </div>
                      ))}
                    </Section>
                  </div>
                )}
              </div>
            )}

          </div>
        )}
      </div>
    </>
  );
}
