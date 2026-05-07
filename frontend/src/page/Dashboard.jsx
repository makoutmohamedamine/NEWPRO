import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import CVUpload from '../components/CVUpload';
import OutlookSync from '../components/OutlookSync';
import {
  getDashboard,
  getGmailDebug,
  getGmailStatus,
  triggerGmailSync,
} from '../api/api';

function toNumber(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : 0;
}

function StatCard({ label, value, sub, color }) {
  return (
    <article className="kpi-card" style={{ '--kpi-color': color || '#b42318' }}>
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
      {sub ? <div className="kpi-sub">{sub}</div> : null}
    </article>
  );
}

export default function Dashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [gmailStatus, setGmailStatus] = useState(null);
  const [gmailSyncing, setGmailSyncing] = useState(false);
  const [gmailMessage, setGmailMessage] = useState('');

  const loadGmailConnection = useCallback(async () => {
    try {
      const gmailRes = await getGmailStatus();
      const statusData = gmailRes?.data || null;
      if (statusData?.connection?.status === 'ok') {
        setGmailStatus(statusData);
        return statusData;
      }
    } catch (_err) {
      // Fallback on debug endpoint when status is unavailable.
    }

    try {
      const debugRes = await getGmailDebug();
      const debugData = debugRes?.data || {};
      const normalized = {
        connection: debugData.connection || { status: 'error' },
        syncHistory: [],
        emailLogs: [],
        totalEmailsProcessed: toNumber(debugData.already_processed),
        totalSyncs: 0,
      };
      setGmailStatus(normalized);
      return normalized;
    } catch (_err) {
      const disconnected = { connection: { status: 'error' } };
      setGmailStatus(disconnected);
      return disconnected;
    }
  }, []);

  const gmailConnected = gmailStatus?.connection?.status === 'ok' && Boolean(gmailStatus?.connection?.mailbox);

  const loadDashboard = useCallback(async () => {
    setError('');
    setLoading(true);
    try {
      const [dashRes] = await Promise.all([getDashboard(), loadGmailConnection()]);
      setDashboard(dashRes.data || {});
    } catch (err) {
      setError(err?.response?.data?.error || 'Impossible de charger le dashboard.');
    } finally {
      setLoading(false);
    }
  }, [loadGmailConnection]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const handleGmailSync = async () => {
    setGmailSyncing(true);
    setGmailMessage('');
    try {
      const res = await triggerGmailSync();
      const report = res.data || {};
      setGmailMessage(
        report.success
          ? `Sync Gmail terminee: ${toNumber(report.cvsCreated)} CV crees, ${toNumber(report.cvsFound)} trouves.`
          : report.errors?.[0] || 'Echec de la synchronisation Gmail.'
      );
      await loadGmailConnection();
      await loadDashboard();
    } catch (err) {
      setGmailMessage(
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        'Echec de la synchronisation Gmail.'
      );
    } finally {
      setGmailSyncing(false);
    }
  };

  const stats = dashboard?.stats || {};
  const topCandidates = dashboard?.topCandidates || [];
  const jobsOverview = dashboard?.jobsOverview || [];
  const scoreDistribution = dashboard?.scoreDistribution || [];
  const slaAlerts = dashboard?.slaAlerts || [];

  const cards = useMemo(
    () => [
      {
        to: '/dossiers-cv',
        title: 'Dossiers CV',
        description: 'Consulter tous les CV classes automatiquement par domaine.',
        cta: 'Voir dossiers CV',
      },
      {
        to: '/candidats',
        title: 'Candidats',
        description: 'Mettre a jour les statuts, visualiser les CV et supprimer si besoin.',
        cta: 'Gerer candidats',
      },
      {
        to: '/postes',
        title: 'Fiches de poste',
        description: 'Creer, modifier et suivre les postes avec leurs seuils de qualification.',
        cta: 'Gerer postes',
      },
      {
        to: '/analyse-ia',
        title: 'Analyse IA',
        description: 'Lancer une analyse IA manuelle de CV et scoring avance.',
        cta: 'Lancer analyse IA',
      },
      {
        to: '/utilisateurs',
        title: 'Utilisateurs',
        description: 'Administrer les comptes et les droits de l application.',
        cta: 'Administrer',
      },
    ],
    []
  );

  return (
    <>
      <div className="page-header">
        <span className="page-header-title">TalentMatch IA</span>
        <div className="page-header-right">
          <button className="btn btn-ghost" type="button" onClick={loadDashboard}>
            Actualiser
          </button>
        </div>
      </div>

      <div className="page-content dashboard-v2">
        {loading ? (
          <div className="empty-state">
            <div className="spinner" style={{ margin: '0 auto 12px' }} />
            Chargement du dashboard...
          </div>
        ) : error ? (
          <div className="alert alert-error">{error}</div>
        ) : (
          <>
            <section className="dashboard-v2-hero">
              <div>
                <div className="hero-eyebrow">Pilotage global</div>
                <h1 className="hero-title compact">Toutes les actions de recrutement en un seul ecran</h1>
                <p className="hero-copy compact">
                  Importez des CV, synchronisez vos boites mail, suivez les statuts et accedez rapidement a chaque module de l application.
                </p>
              </div>
              <div className="dashboard-v2-hero-stats">
                <div className="hero-mini-stat">
                  <strong>{toNumber(stats.totalCandidates)}</strong>
                  <span>Candidats total</span>
                </div>
                <div className="hero-mini-stat">
                  <strong>{toNumber(stats.openJobs)}</strong>
                  <span>Postes ouverts</span>
                </div>
                <div className="hero-mini-stat">
                  <strong>{toNumber(stats.interviewsCount)}</strong>
                  <span>Entretiens en cours</span>
                </div>
                <div className="hero-mini-stat">
                  <strong>{toNumber(stats.overdueActions)}</strong>
                  <span>Actions en retard</span>
                </div>
              </div>
            </section>

            <section className="kpi-grid">
              <StatCard label="Candidatures" value={toNumber(stats.totalApplications)} sub="Total traitees" color="#b42318" />
              <StatCard label="Nouveaux" value={toNumber(stats.newCandidates)} sub="A qualifier" color="#ea580c" />
              <StatCard label="Qualifies" value={toNumber(stats.qualifiedCandidates)} sub="Score >= 70%" color="#15803d" />
              <StatCard label="Score moyen" value={`${toNumber(stats.averageScore).toFixed(1)}%`} sub={`Meilleur ${toNumber(stats.bestScore).toFixed(1)}%`} color="#1d4ed8" />
            </section>

            <section className="dashboard-links-grid">
              {cards.map((item) => (
                <Link key={item.to} to={item.to} className="dashboard-link-card">
                  <div className="dashboard-link-title">{item.title}</div>
                  <div className="dashboard-link-description">{item.description}</div>
                  <div className="dashboard-link-cta">{item.cta}</div>
                </Link>
              ))}
            </section>

            <section className="dashboard-v2-tools">
              <CVUpload onUploadSuccess={loadDashboard} />
              <div style={{ display: 'grid', gap: 16 }}>
                <OutlookSync onSyncSuccess={loadDashboard} />
                <div className="card">
                  <div className="card-header">
                    <span className="card-title">Synchronisation Gmail</span>
                    <span className={`badge ${gmailConnected ? 'badge-green' : 'badge-gray'}`}>
                      {gmailConnected ? 'Connecte' : 'Non connecte'}
                    </span>
                  </div>
                  <div className="card-body" style={{ display: 'grid', gap: 12 }}>
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                      Boite: {gmailStatus?.connection?.mailbox || 'non configuree'}
                    </div>
                    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                      <button className="btn btn-primary" type="button" onClick={handleGmailSync} disabled={gmailSyncing}>
                        {gmailSyncing ? 'Synchronisation...' : 'Lancer sync Gmail'}
                      </button>
                      <button className="btn btn-ghost" type="button" onClick={loadDashboard}>
                        Rafraichir indicateurs
                      </button>
                    </div>
                    {gmailMessage ? (
                      <div className={`alert ${gmailMessage.toLowerCase().includes('echec') ? 'alert-error' : 'alert-success'}`}>
                        {gmailMessage}
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            </section>

            <section className="dashboard-v2-grid">
              <div className="card">
                <div className="card-header">
                  <span className="card-title">Top candidats</span>
                </div>
                <div className="card-body">
                  {topCandidates.length === 0 ? (
                    <div className="empty-state" style={{ padding: '24px 12px' }}>
                      Aucun candidat score pour le moment.
                    </div>
                  ) : (
                    <div className="score-band-list">
                      {topCandidates.map((candidate) => (
                        <div className="score-band-row" key={candidate.id || `${candidate.fullName}-${candidate.email}`}>
                          <div>
                            <div className="score-band-label">{candidate.fullName || 'Candidat'}</div>
                            <div className="score-band-subtitle">
                              {candidate.targetJob || 'Sans poste'} • {candidate.statusLabel || candidate.status || 'Nouveau'}
                            </div>
                          </div>
                          <div className="score-pill" style={{ color: '#15803d', borderColor: '#86efac', background: '#f0fdf4' }}>
                            {toNumber(candidate.matchScore).toFixed(1)}%
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="card">
                <div className="card-header">
                  <span className="card-title">Repartition des scores</span>
                </div>
                <div className="card-body">
                  <div className="score-band-list">
                    {scoreDistribution.map((band) => (
                      <div className="score-band-row" key={band.label}>
                        <div className="score-band-label">{band.label}</div>
                        <div className="badge badge-blue">{toNumber(band.count)} candidat(s)</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </section>

            <section className="dashboard-v2-grid">
              <div className="card">
                <div className="card-header">
                  <span className="card-title">Postes suivis</span>
                </div>
                <div className="card-body">
                  {jobsOverview.length === 0 ? (
                    <div className="empty-state" style={{ padding: '24px 12px' }}>
                      Aucun poste configure.
                    </div>
                  ) : (
                    <div className="table-scroll">
                      <table className="table">
                        <thead>
                          <tr>
                            <th>Poste</th>
                            <th>Candidats</th>
                            <th>Qualifies</th>
                            <th>Score moyen</th>
                          </tr>
                        </thead>
                        <tbody>
                          {jobsOverview.slice(0, 8).map((job) => (
                            <tr key={job.id}>
                              <td>{job.name}</td>
                              <td>{toNumber(job.candidateCount)}</td>
                              <td>{toNumber(job.qualifiedCount)}</td>
                              <td>{toNumber(job.avgScore).toFixed(1)}%</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>

              <div className="card">
                <div className="card-header">
                  <span className="card-title">Alertes SLA</span>
                </div>
                <div className="card-body">
                  {slaAlerts.length === 0 ? (
                    <div className="empty-state" style={{ padding: '24px 12px' }}>
                      Aucune alerte critique.
                    </div>
                  ) : (
                    <div className="alert-list">
                      {slaAlerts.map((item) => (
                        <div key={item.id || `${item.fullName}-${item.targetJob}`} className="alert-item">
                          <div>
                            <div className="alert-item-title">{item.fullName || 'Candidat'}</div>
                            <div className="alert-item-subtitle">{item.targetJob || 'Sans poste'}</div>
                          </div>
                          <div className="badge badge-yellow">{toNumber(item.matchScore).toFixed(1)}%</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </section>
          </>
        )}
      </div>
    </>
  );
}
