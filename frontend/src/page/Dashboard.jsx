import { useEffect, useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import CVUpload from '../components/CVUpload';
import OutlookSync from '../components/OutlookSync';
import { getDashboard } from '../api/api';

const STATUS_COLORS = {
  nouveau: '#b42318',
  prequalifie: '#c2410c',
  shortlist: '#0f766e',
  entretien_rh: '#1d4ed8',
  entretien_technique: '#4f46e5',
  validation_manager: '#7c3aed',
  entretien: '#1d4ed8',
  finaliste: '#7c3aed',
  offre: '#166534',
  accepte: '#15803d',
  refuse: '#6b7280',
  archive: '#94a3b8',
  en_cours: '#d97706',
};

const PIE_COLORS = ['#b42318', '#0f766e', '#1d4ed8', '#7c3aed', '#c2410c', '#334155'];
const CLOSED_STATUSES = new Set(['accepte', 'refuse', 'archive']);

const readField = (obj, ...keys) => {
  for (const key of keys) {
    if (obj?.[key] !== undefined && obj?.[key] !== null) return obj[key];
  }
  return undefined;
};

const toNumber = (value, fallback = 0) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
};

const parseDate = (value) => {
  if (!value) return null;
  const ts = new Date(value).getTime();
  return Number.isNaN(ts) ? null : ts;
};

const normalizeCandidate = (raw = {}, index = 0) => ({
  id: readField(raw, 'id', 'candidateId', 'candidate_id') ?? `cand-${index}`,
  fullName: readField(raw, 'fullName', 'full_name', 'name') || [raw?.prenom, raw?.nom].filter(Boolean).join(' ') || 'Candidat',
  email: readField(raw, 'email', 'mail') || '-',
  targetJob: readField(raw, 'targetJob', 'target_job', 'poste', 'profileLabel') || '',
  workflowStep: readField(raw, 'workflowStep', 'workflow_step') || 'Evaluation RH',
  recommendation: readField(raw, 'recommendation', 'recommandation') || 'A evaluer',
  status: readField(raw, 'status', 'statut') || 'nouveau',
  statusLabel: readField(raw, 'statusLabel', 'status_label') || 'Nouveau',
  matchScore: toNumber(readField(raw, 'matchScore', 'score', 'score_global')),
  slaDueAt: readField(raw, 'slaDueAt', 'sla_due_at') || null,
  createdAt: readField(raw, 'createdAt', 'created_at') || null,
  updatedAt: readField(raw, 'updatedAt', 'updated_at') || null,
});

const normalizePayload = (payload = {}) => {
  const candidates = Array.isArray(payload?.candidates) ? payload.candidates.map(normalizeCandidate) : [];
  return {
    ...payload,
    candidates,
    topCandidates: Array.isArray(payload?.topCandidates) ? payload.topCandidates.map(normalizeCandidate) : [],
    slaAlerts: Array.isArray(payload?.slaAlerts) ? payload.slaAlerts.map(normalizeCandidate) : [],
    funnel: Array.isArray(payload?.funnel) ? payload.funnel : [],
    scoreDistribution: Array.isArray(payload?.scoreDistribution) ? payload.scoreDistribution : [],
    jobsOverview: Array.isArray(payload?.jobsOverview)
      ? payload.jobsOverview.map((job) => ({
          ...job,
          candidateCount: toNumber(job?.candidateCount),
          qualifiedCount: toNumber(job?.qualifiedCount),
          avgScore: toNumber(job?.avgScore),
        }))
      : [],
    profileDistribution: payload?.profileDistribution || {},
  };
};

function MetricCard({ title, value, subtitle, color }) {
  return (
    <article className="kpi-card" style={{ '--kpi-color': color }}>
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{title}</div>
      <div className="kpi-sub">{subtitle}</div>
    </article>
  );
}

function ScorePill({ score }) {
  const value = toNumber(score);
  const tone = value >= 85 ? '#15803d' : value >= 70 ? '#0f766e' : value >= 50 ? '#c2410c' : '#b42318';
  return (
    <span className="score-pill" style={{ color: tone, borderColor: `${tone}33`, background: `${tone}12` }}>
      {value.toFixed(1)}%
    </span>
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
      .then((res) => setData(normalizePayload(res.data)))
      .catch((err) => setError(err?.response?.data?.error || 'Impossible de charger le dashboard.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const stats = data?.stats || {};
  const profileDistribution = useMemo(
    () => Object.entries(data?.profileDistribution || {}).map(([name, value]) => ({ name, value })),
    [data]
  );
  const jobsOverview = Array.isArray(data?.jobsOverview) ? data.jobsOverview : [];
  const funnel = Array.isArray(data?.funnel) ? data.funnel : [];
  const scoreDistribution = Array.isArray(data?.scoreDistribution) ? data.scoreDistribution : [];
  const allCandidates = useMemo(() => (Array.isArray(data?.candidates) ? data.candidates : []), [data]);

  const filteredCandidates = useMemo(() => {
    const now = Date.now();
    const rangeMsMap = { '7d': 7 * 86400000, '30d': 30 * 86400000, '90d': 90 * 86400000 };
    const rangeMs = rangeMsMap[dateRange] || null;

    return [...allCandidates]
      .filter((candidate) => {
        if (!rangeMs) return true;
        const ts = parseDate(candidate.updatedAt || candidate.createdAt);
        if (!ts) return true;
        return now - ts <= rangeMs;
      })
      .sort((a, b) => {
        const ta = parseDate(a.updatedAt || a.createdAt) || 0;
        const tb = parseDate(b.updatedAt || b.createdAt) || 0;
        return dateSort === 'asc' ? ta - tb : tb - ta;
      });
  }, [allCandidates, dateRange, dateSort]);

  const topCandidates = useMemo(() => {
    if (Array.isArray(data?.topCandidates) && data.topCandidates.length) return data.topCandidates.slice(0, 6);
    return [...filteredCandidates].sort((a, b) => b.matchScore - a.matchScore).slice(0, 6);
  }, [data, filteredCandidates]);

  const alerts = useMemo(() => {
    if (Array.isArray(data?.slaAlerts) && data.slaAlerts.length) return data.slaAlerts.slice(0, 6);
    return filteredCandidates.filter((c) => c.slaDueAt && !CLOSED_STATUSES.has(c.status)).slice(0, 6);
  }, [data, filteredCandidates]);

  const lastSyncDate = new Date().toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' });

  if (loading) {
    return (
      <>
        <div className="page-header">
          <span className="page-header-title">Dashboard recrutement</span>
        </div>
        <div className="page-content empty-state">
          <div className="spinner" style={{ margin: '0 auto 12px' }} />
          Chargement des donnees...
        </div>
      </>
    );
  }

  if (error) {
    return (
      <>
        <div className="page-header">
          <span className="page-header-title">Dashboard recrutement</span>
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
        <span className="page-header-title">Dashboard recrutement</span>
        <div className="page-header-right dashboard-header-wrap">
          <div className="dashboard-filter-bar">
            <select className="dashboard-filter-select" value={dateRange} onChange={(e) => setDateRange(e.target.value)}>
              <option value="all">Toutes les dates</option>
              <option value="7d">7 derniers jours</option>
              <option value="30d">30 derniers jours</option>
              <option value="90d">90 derniers jours</option>
            </select>
            <select className="dashboard-filter-select" value={dateSort} onChange={(e) => setDateSort(e.target.value)}>
              <option value="desc">Plus recent d'abord</option>
              <option value="asc">Plus ancien d'abord</option>
            </select>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={load}>Actualiser</button>
        </div>
      </div>

      <div className="page-content dashboard-v2">
        <section className="dashboard-v2-hero">
          <div>
            <div className="hero-eyebrow">Vue operationnelle</div>
            <h1 className="hero-title compact">Pilotage en temps reel des candidatures.</h1>
            <p className="hero-copy compact">
              Donnees synchronisees avec l'API: candidats, pipeline, postes, alertes de traitement et performance de matching.
            </p>
          </div>
          <div className="dashboard-v2-hero-stats">
            <div className="hero-mini-stat">
              <strong>{toNumber(stats.totalCandidates)}</strong>
              <span>candidats</span>
            </div>
            <div className="hero-mini-stat">
              <strong>{toNumber(stats.openJobs)}</strong>
              <span>postes ouverts</span>
            </div>
            <div className="hero-mini-stat">
              <strong>{toNumber(stats.overdueActions)}</strong>
              <span>alertes SLA</span>
            </div>
            <div className="hero-mini-stat">
              <strong>{lastSyncDate}</strong>
              <span>derniere vue</span>
            </div>
          </div>
        </section>

        <section className="kpi-grid">
          <MetricCard title="Candidatures" value={toNumber(stats.totalApplications)} subtitle="volume total traite" color="#0f766e" />
          <MetricCard title="Score moyen" value={`${toNumber(stats.averageScore).toFixed(1)}%`} subtitle="qualite moyenne" color="#1d4ed8" />
          <MetricCard title="Entretiens" value={toNumber(stats.interviewsCount)} subtitle="phases actives" color="#7c3aed" />
          <MetricCard title="Acceptes" value={toNumber(stats.acceptedCandidates)} subtitle="dossiers conclus" color="#15803d" />
          <MetricCard title="Nouveaux" value={toNumber(stats.newCandidates)} subtitle="a traiter" color="#b42318" />
          <MetricCard title="Delai moyen" value={`${toNumber(stats.processingDelayHours).toFixed(1)} h`} subtitle="temps de traitement" color="#c2410c" />
        </section>

        <section className="dashboard-v2-tools">
          <CVUpload onUploadSuccess={load} />
          <OutlookSync onSyncSuccess={load} />
        </section>

        <section className="dashboard-v2-grid">
          <div className="card">
            <div className="card-header">
              <span className="card-title">Pipeline de recrutement</span>
            </div>
            <div className="card-body chart-body">
              <ResponsiveContainer width="100%" height={280}>
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
              <span className="card-title">Repartition par profils</span>
            </div>
            <div className="card-body chart-body">
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie data={profileDistribution} dataKey="value" nameKey="name" innerRadius={58} outerRadius={95}>
                    {profileDistribution.map((item, index) => (
                      <Cell key={`${item.name}-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        </section>

        <section className="dashboard-v2-grid">
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
                    <strong>{toNumber(band.count)}</strong>
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
              {alerts.length === 0 ? (
                <div className="empty-state" style={{ padding: '20px 12px' }}>Aucune alerte active.</div>
              ) : (
                <div className="alert-list">
                  {alerts.map((candidate) => (
                    <div key={candidate.id} className="alert-item">
                      <div>
                        <div className="alert-item-title">{candidate.fullName}</div>
                        <div className="alert-item-subtitle">{candidate.targetJob || 'Poste non defini'} - {candidate.workflowStep}</div>
                      </div>
                      <ScorePill score={candidate.matchScore} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>

        <section className="dashboard-v2-grid">
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
                      <td>{candidate.targetJob || '-'}</td>
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
              <span className="card-title">Couverture des postes</span>
            </div>
            <div className="table-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>Poste</th>
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
                        <div className="table-subtext">{job.location || 'Localisation non definie'}</div>
                      </td>
                      <td><span className="badge badge-black">{job.priority || '-'}</span></td>
                      <td>{toNumber(job.candidateCount)}</td>
                      <td>{toNumber(job.qualifiedCount)}</td>
                      <td>{toNumber(job.avgScore).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
