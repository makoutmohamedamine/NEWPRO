import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { getDossiers } from '../api/api';

function CandidateLine({ candidate }) {
  return (
    <div className="folder-candidate-card">
      <div className="folder-candidate-top">
        <div>
          <div className="folder-candidate-name">{candidate.fullName}</div>
          <div className="folder-candidate-meta">{candidate.email}</div>
        </div>
        <strong>{Number(candidate.matchScore || 0).toFixed(1)}%</strong>
      </div>
      <div className="folder-candidate-tags">
        <span className="badge badge-gray">{candidate.statusLabel}</span>
        <span className="badge badge-gray">{candidate.recommendation}</span>
      </div>
      <div className="folder-candidate-summary">{candidate.summary || 'Resume indisponible.'}</div>
    </div>
  );
}

export default function Dossiers() {
  const [folders, setFolders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    getDossiers()
      .then((res) => setFolders(res.data.dossiers || []))
      .catch((err) => setError(err?.response?.data?.error || 'Impossible de charger les dossiers.'))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(
    () => folders.filter((folder) => folder.titre.toLowerCase().includes(query.toLowerCase())),
    [folders, query]
  );

  const totalCandidates = folders.reduce((sum, folder) => sum + (folder.totalCvs || 0), 0);

  return (
    <>
      <div className="page-header">
        <span className="page-header-title">Dossiers par poste</span>
        <div className="page-header-right">
          <input
            className="form-input"
            style={{ width: 260 }}
            placeholder="Rechercher un poste..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
      </div>

      <div className="page-content">
        {!loading && !error && (
          <div className="candidate-toolbar-summary">
            <div className="candidate-toolbar-stat">
              <strong>{folders.length}</strong>
              <span>Postes suivis</span>
            </div>
            <div className="candidate-toolbar-stat">
              <strong>{totalCandidates}</strong>
              <span>Candidatures rattachees</span>
            </div>
            <div className="candidate-toolbar-stat">
              <strong>{filtered.length}</strong>
              <span>Colonnes affichees</span>
            </div>
          </div>
        )}

        {loading ? (
          <div className="empty-state">
            <div className="spinner" style={{ margin: '0 auto 12px' }} />
            Chargement des dossiers...
          </div>
        ) : error ? (
          <div className="alert alert-error">{error}</div>
        ) : folders.length === 0 ? (
          <div className="workflow-empty">
            <div className="workflow-empty-icon">D</div>
            <div className="workflow-empty-title">Aucun poste n a encore ete prepare</div>
            <div className="workflow-empty-copy">
              Cree d abord une fiche de poste pour generer une colonne de workflow, puis importe des CV depuis le dashboard.
            </div>
            <div className="workflow-empty-actions">
              <Link className="btn btn-primary" to="/postes">Creer un poste</Link>
              <Link className="btn btn-ghost" to="/">Aller au dashboard</Link>
            </div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="workflow-empty">
            <div className="workflow-empty-icon">?</div>
            <div className="workflow-empty-title">Aucun poste ne correspond a la recherche</div>
            <div className="workflow-empty-copy">
              Essaie un autre mot-cle ou vide la recherche pour afficher toutes les colonnes.
            </div>
            <div className="workflow-empty-actions">
              <button className="btn btn-primary" type="button" onClick={() => setQuery('')}>Reinitialiser la recherche</button>
            </div>
          </div>
        ) : (
          <div className="folder-board">
            {filtered.map((folder) => (
              <section className="folder-column" key={folder.id}>
                <div className="folder-column-head">
                  <div>
                    <div className="folder-column-title">{folder.titre}</div>
                    <div className="folder-column-meta">
                      {folder.localisation || 'Localisation libre'} • seuil {folder.seuilQualification}%
                    </div>
                  </div>
                  <span className="badge badge-black">{folder.priorite}</span>
                </div>

                <div className="folder-column-stats">
                  <div><span>Total</span><strong>{folder.totalCvs}</strong></div>
                  <div><span>Nouveaux</span><strong>{folder.nouveaux}</strong></div>
                  <div><span>Entretiens</span><strong>{folder.entretiens}</strong></div>
                  <div><span>Top</span><strong>{folder.bestScore}%</strong></div>
                </div>

                <div className="folder-column-list">
                  {folder.cvs.length > 0 ? (
                    folder.cvs.map((candidate) => <CandidateLine key={candidate.id} candidate={candidate} />)
                  ) : (
                    <div className="empty-state" style={{ padding: '18px 10px' }}>
                      Aucun candidat sur ce poste.
                    </div>
                  )}
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
