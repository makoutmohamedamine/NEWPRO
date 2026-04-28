import { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import CVUpload from '../components/CVUpload';
import OutlookSync from '../components/OutlookSync';
import { getDashboard } from '../api/api';

const STATUS_COLORS = {
  nouveau: '#b42318',
  prequalifie: '#c2410c',
  shortlist: '#0f766e',
  entretien: '#1d4ed8',
  finaliste: '#7c3aed',
  offre: '#166534',
  accepte: '#15803d',
  refuse: '#6b7280',
  archive: '#94a3b8',
  en_cours: '#d97706',
};

function KpiCard({ value, label, sub, tone = 'var(--accent)' }) {
  return (
    <div className="kpi-card" style={{ '--kpi-color': tone }}>
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

function ScorePill({ score }) {
  const numeric = Number(score || 0);
  const tone = numeric >= 85 ? '#15803d' : numeric >= 70 ? '#0f766e' : numeric >= 50 ? '#c2410c' : '#b42318';
  return (
    <span className="score-pill" style={{ color: tone, borderColor: `${tone}33`, background: `${tone}10` }}>
      {numeric.toFixed(1)}%
    </span>
  );
}

function QuickStat({ value, label }) {
  return (
    <div className="hero-mini-stat">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [dateRange, setDateRange] = useState('all');
  const [dateSort, setDateSort] = useState('desc');

  const load = () => {
    setLoading(true);
    setError('');
    getDashboard()
      .then((res) => setData(res.data))
      .catch((err) => setError(err?.response?.data?.error || 'Impossible de charger le dashboard.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const stats = data?.stats || {};
  const funnel = data?.funnel || [];
  const scoreDistribution = data?.scoreDistribution || [];
  const jobsOverview = data?.jobsOverview || [];
  const profileDistribution = Object.entries(data?.profileDistribution || {}).map(([name, value]) => ({ name, value }));
  const allCandidates = data?.candidates || [];

  const filteredCandidates = useMemo(() => {
    const now = Date.now();
    const rangeMsMap = {
      '7d': 7 * 24 * 60 * 60 * 1000,
      '30d': 30 * 24 * 60 * 60 * 1000,
      '90d': 90 * 24 * 60 * 60 * 1000,
    };
    const rangeMs = rangeMsMap[dateRange] || null;
    const withDate = allCandidates.filter((item) => {
      const iso = item?.updatedAt || item?.createdAt;
      if (!iso) return false;
      const ts = new Date(iso).getTime();
      if (Number.isNaN(ts)) return false;
      if (!rangeMs) return true;
      return now - ts <= rangeMs;
    });

    withDate.sort((a, b) => {
      const ta = new Date(a.updatedAt || a.createdAt).getTime();
      const tb = new Date(b.updatedAt || b.createdAt).getTime();
      return dateSort === 'asc' ? ta - tb : tb - ta;
    });
    return withDate;
  }, [allCandidates, dateRange, dateSort]);

  const topCandidates = useMemo(
    () => [...filteredCandidates].sort((a, b) => (b.matchScore || 0) - (a.matchScore || 0)).slice(0, 5),
    [filteredCandidates]
  );
  const alerts = useMemo(
    () => filteredCandidates.filter((c) => c.slaDueAt && ['accepte', 'refuse', 'archive'].includes(c.status) === false).slice(0, 6),
    [filteredCandidates]
  );

  if (loading) {
    return (
      <>
        <div className="page-header">
          <span className="page-header-title">Tableau de bord RH</span>
        </div>
        <div className="page-content empty-state">
          <div className="spinner" style={{ margin: '0 auto 12px' }} />
          Chargement du cockpit recrutement...
        </div>
      </>
    );
  }

  if (error) {
    return (
      <>
        <div className="page-header">
          <span className="page-header-title">Tableau de bord RH</span>
        </div>
        <div className="page-content">
          <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>
          <button className="btn btn-primary" onClick={load}>Reessayer</button>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="page-header">
        <span className="page-header-title">Tableau de bord RH</span>
        <div className="page-header-right">
          <div className="dashboard-filter-bar">
            <select className="dashboard-filter-select" value={dateRange} onChange={(e) => setDateRange(e.target.value)}>
              <option value="all">Toutes les dates</option>
              <option value="7d">7 derniers jours</option>
              <option value="30d">30 derniers jours</option>
              <option value="90d">90 derniers jours</option>
            </select>
            <select className="dashboard-filter-select" value={dateSort} onChange={(e) => setDateSort(e.target.value)}>
              <option value="desc">Plus récent d'abord</option>
              <option value="asc">Plus ancien d'abord</option>
            </select>
          </div>
          <span className="dashboard-datetime">
            {new Date().toLocaleDateString('fr-FR', {
              weekday: 'long',
              day: 'numeric',
              month: 'long',
              year: 'numeric',
            })}
          </span>
        </div>
      </div>

      <div className="page-content dashboard-layout">
        <section className="dashboard-tools-row card card-body">
          <div>
            <div className="card-title">Tri par date</div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.82rem', marginTop: 4 }}>
              Filtrer les candidats affichés selon la période.
            </div>
          </div>
          <div className="dashboard-filter-bar">
            <select className="dashboard-filter-select" value={dateRange} onChange={(e) => setDateRange(e.target.value)}>
              <option value="all">Toutes les dates</option>
              <option value="7d">7 derniers jours</option>
              <option value="30d">30 derniers jours</option>
              <option value="90d">90 derniers jours</option>
            </select>
            <select className="dashboard-filter-select" value={dateSort} onChange={(e) => setDateSort(e.target.value)}>
              <option value="desc">Plus récent d'abord</option>
              <option value="asc">Plus ancien d'abord</option>
            </select>
          </div>
        </section>

        <section className="dashboard-hero-compact">
          <div className="dashboard-hero-copy">
            <div className="hero-eyebrow">CDC RH - automatisation recrutement</div>
            <h1 className="hero-title compact">Cockpit de traitement des candidatures et du workflow RH.</h1>
            <p className="hero-copy compact">
              Vue synthese des CV recus, des dossiers par poste, des alertes SLA et du niveau de qualification.
            </p>
          </div>
          <div className="dashboard-hero-metrics">
            <QuickStat value={stats.qualifiedCandidates || 0} label="candidats qualifies" />
            <QuickStat value={stats.overdueActions || 0} label="alertes SLA" />
            <QuickStat value={stats.openJobs || 0} label="postes ouverts" />
          </div>
        </section>

        <div className="kpi-grid">
          <KpiCard value={stats.totalCandidates || 0} label="Candidats" sub="dans la base" />
          <KpiCard value={stats.totalApplications || 0} label="Candidatures" sub="toutes sources" tone="#0f766e" />
          <KpiCard value={`${(stats.averageScore || 0).toFixed(1)}%`} label="Score moyen" sub="matching CDC" tone="#1d4ed8" />
          <KpiCard value={stats.interviewsCount || 0} label="Entretiens" sub="en cours ou planifies" tone="#7c3aed" />
          <KpiCard value={stats.newCandidates || 0} label="Nouveaux" sub="a traiter rapidement" tone="#b42318" />
          <KpiCard value={`${(stats.processingDelayHours || 0).toFixed(1)} h`} label="Delai moyen" sub="du traitement RH" tone="#c2410c" />
        </div>

        <div className="dashboard-actions-grid">
          <CVUpload onUploadSuccess={load} />
          <OutlookSync onSyncSuccess={load} />
        </div>

        <div className="dashboard-grid-2">
          <div className="card">
            <div className="card-header">
              <span className="card-title">Entonnoir de workflow</span>
            </div>
            <div className="card-body chart-body">
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={funnel}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                    {funnel.map((item) => (
                      <Cell key={item.key} fill={STATUS_COLORS[item.key] || '#1f2937'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <span className="card-title">Repartition des profils</span>
            </div>
            <div className="card-body chart-body">
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={profileDistribution} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90}>
                    {profileDistribution.map((item, index) => (
                      <Cell
                        key={`${item.name}-${index}`}
                        fill={['#b42318', '#0f766e', '#1d4ed8', '#7c3aed', '#c2410c', '#334155'][index % 6]}
                      />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        <div className="dashboard-grid-2">
          <div className="card">
            <div className="card-header">
              <span className="card-title">Distribution des scores</span>
            </div>
            <div className="card-body">
              <div className="score-band-list">
                {scoreDistribution.map((band) => (
                  <div key={band.label} className="score-band-row">
                    <div>
                      <div className="score-band-label">{band.label}</div>
                      <div className="score-band-subtitle">candidatures</div>
                    </div>
                    <strong>{band.count}</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <span className="card-title">Alertes prioritaires</span>
            </div>
            <div className="card-body">
              {alerts.length > 0 ? (
                <div className="alert-list">
                  {alerts.map((candidate) => (
                    <div key={candidate.id} className="alert-item">
                      <div>
                        <div className="alert-item-title">{candidate.fullName}</div>
                        <div className="alert-item-subtitle">
                          {candidate.targetJob || 'Poste non defini'} • {candidate.workflowStep}
                        </div>
                      </div>
                      <ScorePill score={candidate.matchScore} />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state" style={{ padding: '24px 12px' }}>
                  Aucun profil critique en attente.
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="dashboard-grid-2">
          <div className="card">
            <div className="card-header">
              <span className="card-title">Top candidats</span>
            </div>
            <div className="table-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>Candidat</th>
                    <th>Poste</th>
                    <th>Recommandation</th>
                    <th>Statut</th>
                    <th>Score</th>
                  </tr>
                </thead>
                <tbody>
                  {topCandidates.map((candidate) => (
                    <tr key={candidate.id}>
                      <td>
                        <div className="table-name">{candidate.fullName}</div>
                        <div className="table-subtext">{candidate.email}</div>
                      </td>
                      <td>{candidate.targetJob || 'Auto'}</td>
                      <td>{candidate.recommendation}</td>
                      <td><span className="badge badge-gray">{candidate.statusLabel}</span></td>
                      <td><ScorePill score={candidate.matchScore} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <span className="card-title">Vue postes et couverture</span>
            </div>
            <div className="table-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>Poste</th>
                    <th>Localisation</th>
                    <th>Priorite</th>
                    <th>Candidatures</th>
                    <th>Qualifies</th>
                    <th>Score moyen</th>
                  </tr>
                </thead>
                <tbody>
                  {jobsOverview.map((job) => (
                    <tr key={job.id}>
                      <td>
                        <div className="table-name">{job.name}</div>
                        <div className="table-subtext">{job.department || 'Recrutement general'}</div>
                      </td>
                      <td>{job.location || 'Non defini'}</td>
                      <td><span className="badge badge-black">{job.priority}</span></td>
                      <td>{job.candidateCount}</td>
                      <td>{job.qualifiedCount}</td>
                      <td>{job.avgScore.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
