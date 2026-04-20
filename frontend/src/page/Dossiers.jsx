import { useEffect, useState } from 'react';
import { getDossiers } from '../api/api';

const DOMAIN_ICONS = {
  'Développeur Full Stack':  '💻',
  'Developpeur Full Stack':  '💻',
  'Data Analyst':            '📊',
  'Ingénieur IA/NLP':       '🤖',
  'Ingenieur IA/NLP':       '🤖',
  'Marketing Digital':       '📣',
  'Développeur Backend':    '⚙️',
  'Developpeur Backend':    '⚙️',
  'DevOps / Cloud':          '☁️',
};

const STATUT_META = {
  nouveau:  { badge: 'badge-red',    label: 'Nouveau' },
  en_cours: { badge: 'badge-yellow', label: 'En cours' },
  accepte:  { badge: 'badge-green',  label: 'Accepté' },
  refuse:   { badge: 'badge-gray',   label: 'Refusé' },
};

function ScoreBar({ score }) {
  const pct = Math.min(parseFloat(score) || 0, 100);
  return (
    <div className="score-bar-wrap">
      <div className="score-bar-track">
        <div className="score-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="score-num">{pct.toFixed(1)}%</span>
    </div>
  );
}

function CvRow({ cv }) {
  const meta = STATUT_META[cv.statut] || { badge: 'badge-gray', label: cv.statut };
  return (
    <tr>
      <td>
        <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>{cv.fullName}</div>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{cv.email}</div>
      </td>
      <td>
        <span className={`badge ${meta.badge}`}>{meta.label}</span>
      </td>
      <td>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 5,
          fontSize: '0.78rem',
          color: cv.source === 'outlook' ? '#1d4ed8' : 'var(--text-muted)',
        }}>
          {cv.source === 'outlook' ? '✉ Outlook' : '⬆ Manuel'}
        </span>
        {cv.sourceEmail && (
          <div style={{ fontSize: '0.7rem', color: 'var(--gray-400)' }}>{cv.sourceEmail}</div>
        )}
      </td>
      <td style={{ minWidth: 150 }}>
        <ScoreBar score={cv.score} />
      </td>
      <td style={{ whiteSpace: 'nowrap', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
        {new Date(cv.createdAt).toLocaleDateString('fr-FR')}
      </td>
      <td>
        {cv.cvUrl ? (
          <a
            href={`http://127.0.0.1:8000${cv.cvUrl}`}
            target="_blank"
            rel="noreferrer"
            className="btn btn-outline btn-sm"
          >
            ↓ CV
          </a>
        ) : (
          <span style={{ fontSize: '0.75rem', color: 'var(--gray-400)' }}>—</span>
        )}
      </td>
    </tr>
  );
}

function DossierCard({ dossier, isOpen, onToggle }) {
  const icon = DOMAIN_ICONS[dossier.titre] || '📁';
  const outlookCvs = dossier.cvs.filter(c => c.source === 'outlook');

  return (
    <div className={`folder-card${isOpen ? ' open' : ''}`}>
      {/* En-tête du dossier */}
      <div className="folder-card-header" onClick={onToggle}>
        <div className="folder-icon">{icon}</div>
        <div style={{ flex: 1 }}>
          <div className="folder-name">{dossier.titre}</div>
          <div className="folder-desc">{dossier.description || 'Aucune description'}</div>
          {dossier.nouveaux > 0 && (
            <span className="badge badge-red" style={{ marginTop: 6 }}>
              {dossier.nouveaux} nouveau{dossier.nouveaux > 1 ? 'x' : ''}
            </span>
          )}
        </div>
        <span style={{
          color: 'var(--text-muted)', fontSize: '1rem',
          transform: isOpen ? 'rotate(90deg)' : 'none',
          transition: 'transform 0.2s',
          flexShrink: 0,
        }}>›</span>
      </div>

      {/* Statistiques */}
      <div className="folder-stats">
        <div className="folder-stat">
          <span className="folder-stat-val">{dossier.totalCvs}</span>
          <span className="folder-stat-label">Total CV</span>
        </div>
        <div className="folder-stat">
          <span className="folder-stat-val" style={{ color: 'var(--red)' }}>{outlookCvs.length}</span>
          <span className="folder-stat-label">Via Outlook</span>
        </div>
        <div className="folder-stat">
          <span className="folder-stat-val" style={{ color: '#16a34a' }}>{dossier.acceptes}</span>
          <span className="folder-stat-label">Acceptés</span>
        </div>
        <div className="folder-stat">
          <span className="folder-stat-val">{dossier.bestScore}%</span>
          <span className="folder-stat-label">Top score</span>
        </div>
      </div>

      {/* Liste des CVs — affichée si le dossier est ouvert */}
      {isOpen && (
        <div className="folder-cv-list">
          {dossier.cvs.length > 0 ? (
            <table className="table">
              <thead>
                <tr>
                  <th>Candidat</th>
                  <th>Statut</th>
                  <th>Source</th>
                  <th>Score ML</th>
                  <th>Date</th>
                  <th>Fichier</th>
                </tr>
              </thead>
              <tbody>
                {dossier.cvs.map((cv) => (
                  <CvRow key={cv.candidatureId} cv={cv} />
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty-state" style={{ padding: '2rem' }}>
              <div className="empty-state-icon">📭</div>
              <div className="empty-state-title">Aucun CV dans ce dossier</div>
              <div style={{ fontSize: '0.8rem' }}>
                Les CVs reçus via Outlook apparaîtront ici automatiquement.
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Dossiers() {
  const [dossiers, setDossiers] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [openId, setOpenId]     = useState(null);
  const [search, setSearch]     = useState('');

  useEffect(() => {
    getDossiers()
      .then(r => setDossiers(r.data.dossiers || []))
      .catch(() => setError('Impossible de charger les dossiers.'))
      .finally(() => setLoading(false));
  }, []);

  const filtered = dossiers.filter(d =>
    d.titre.toLowerCase().includes(search.toLowerCase())
  );

  const totalCvs    = dossiers.reduce((s, d) => s + d.totalCvs, 0);
  const totalOutlook = dossiers.reduce((s, d) => s + d.outlookCvs, 0);
  const totalNew    = dossiers.reduce((s, d) => s + d.nouveaux, 0);

  return (
    <>
      {/* Header */}
      <div className="page-header">
        <span className="page-header-title">Dossiers par domaine</span>
        <div className="page-header-right">
          <input
            className="form-input"
            style={{ width: 220, padding: '6px 12px' }}
            placeholder="Rechercher un domaine…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="page-content">

        {/* Résumé global */}
        {!loading && !error && (
          <div className="kpi-grid" style={{ marginBottom: 24 }}>
            <div className="kpi-card" style={{ '--kpi-color': 'var(--red)' }}>
              <div className="kpi-value">{dossiers.length}</div>
              <div className="kpi-label">Domaines</div>
            </div>
            <div className="kpi-card" style={{ '--kpi-color': '#1a1a1a' }}>
              <div className="kpi-value">{totalCvs}</div>
              <div className="kpi-label">CVs total</div>
            </div>
            <div className="kpi-card" style={{ '--kpi-color': '#1d4ed8' }}>
              <div className="kpi-value">{totalOutlook}</div>
              <div className="kpi-label">Via Outlook</div>
            </div>
            <div className="kpi-card" style={{ '--kpi-color': 'var(--red)' }}>
              <div className="kpi-value">{totalNew}</div>
              <div className="kpi-label">Non traités</div>
            </div>
          </div>
        )}

        {/* États */}
        {loading && (
          <div className="empty-state">
            <div className="spinner" style={{ margin: '0 auto 12px' }} />
            Chargement des dossiers…
          </div>
        )}
        {error && <div className="alert alert-error">{error}</div>}

        {/* Grille de dossiers */}
        {!loading && !error && (
          filtered.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {filtered.map(d => (
                <DossierCard
                  key={d.id}
                  dossier={d}
                  isOpen={openId === d.id}
                  onToggle={() => setOpenId(openId === d.id ? null : d.id)}
                />
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-state-icon">🗂️</div>
              <div className="empty-state-title">Aucun dossier trouvé</div>
              <div style={{ fontSize: '0.875rem', marginTop: 6 }}>
                Créez des postes depuis la page <strong>Postes</strong> pour générer des dossiers.
              </div>
            </div>
          )
        )}
      </div>
    </>
  );
}
