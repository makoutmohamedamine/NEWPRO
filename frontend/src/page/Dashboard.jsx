import { useEffect, useState } from 'react';
import { getDashboard } from '../api/api';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts';

const PIE_COLORS = ['#dc2626', '#1a1a1a', '#6b7280', '#b91c1c', '#9ca3af', '#374151'];

const STATUT_META = {
  nouveau:  { label: 'Nouveaux',  color: '#dc2626' },
  en_cours: { label: 'En cours',  color: '#f59e0b' },
  accepte:  { label: 'Acceptés',  color: '#16a34a' },
  refuse:   { label: 'Refusés',   color: '#6b7280' },
};

function KpiCard({ value, label, sub, color = 'var(--red)' }) {
  return (
    <div className="kpi-card" style={{ '--kpi-color': color }}>
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

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

export default function Dashboard() {
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);

  const load = () => {
    setLoading(true);
    setError(null);
    getDashboard()
      .then(r => setData(r.data))
      .catch(e => {
        const msg = e?.response?.data?.error || e?.message || 'Erreur réseau';
        setError(msg);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  if (loading) return (
    <>
      <div className="page-header"><span className="page-header-title">Dashboard</span></div>
      <div className="page-content empty-state">
        <div className="spinner" style={{ margin: '0 auto 12px' }} />
        Chargement…
      </div>
    </>
  );

  if (error) return (
    <>
      <div className="page-header"><span className="page-header-title">Dashboard</span></div>
      <div className="page-content">
        <div style={{
          background: '#fee2e2', color: '#991b1b', borderRadius: 10,
          padding: '20px 24px', display: 'flex', alignItems: 'center', gap: 16,
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Impossible de charger le tableau de bord</div>
            <div style={{ fontSize: '0.82rem', opacity: 0.8 }}>{error}</div>
            <div style={{ fontSize: '0.78rem', marginTop: 6, opacity: 0.7 }}>
              Vérifiez que le serveur Django est démarré sur le port 8000.
            </div>
          </div>
          <button
            className="btn btn-primary"
            onClick={load}
            style={{ flexShrink: 0, background: '#dc2626', borderColor: '#dc2626' }}
          >
            Réessayer
          </button>
        </div>
      </div>
    </>
  );

  const stats        = data?.stats || {};
  const topCandidates = data?.topCandidates || [];
  const profileDist  = data?.profileDistribution || {};
  const statusDist   = data?.statusDistribution || {};

  const barData = topCandidates.slice(0, 8).map(c => ({
    name: (c.fullName || '').split(' ')[0] || `#${c.id}`,
    score: parseFloat(c.matchScore || 0),
  }));

  const pieData = Object.entries(profileDist)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }));

  const statusRows = Object.entries(statusDist).map(([key, count]) => ({
    key, count,
    ...(STATUT_META[key] || { label: key, color: '#9ca3af' }),
  }));

  const totalStatus = statusRows.reduce((s, r) => s + r.count, 0);

  return (
    <>
      {/* Header */}
      <div className="page-header">
        <span className="page-header-title">Tableau de bord</span>
        <div className="page-header-right">
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' })}
          </span>
        </div>
      </div>

      <div className="page-content">

        {/* ── KPIs ── */}
        <div className="kpi-grid">
          <KpiCard
            value={stats.totalCandidates ?? 0}
            label="Total candidats"
            sub="dans la base"
            color="var(--red)"
          />
          <KpiCard
            value={stats.newCandidates ?? 0}
            label="Nouveaux"
            sub="en attente de traitement"
            color="#1a1a1a"
          />
          <KpiCard
            value={stats.averageScore ? stats.averageScore.toFixed(1) + '%' : '—'}
            label="Score ML moyen"
            sub="matching CV / poste"
            color="#dc2626"
          />
          <KpiCard
            value={stats.bestScore ? stats.bestScore.toFixed(1) + '%' : '—'}
            label="Meilleur score"
            sub="top candidat"
            color="#6b7280"
          />
        </div>

        {/* ── Graphiques ── */}
        <div className="chart-grid">

          {/* Barres — Top candidats */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Top candidats — Score ML</span>
            </div>
            <div className="card-body">
              {barData.length > 0 ? (
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={barData} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#6b7280' }} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#6b7280' }} unit="%" />
                    <Tooltip
                      formatter={v => [`${v.toFixed(1)}%`, 'Score']}
                      contentStyle={{ borderRadius: 8, border: '1px solid #e5e7eb', fontSize: 12 }}
                    />
                    <Bar dataKey="score" fill="#dc2626" radius={[4, 4, 0, 0]} maxBarSize={40} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="empty-state" style={{ padding: '3rem 0' }}>
                  <div className="empty-state-icon">📊</div>
                  <div className="empty-state-title">Aucun candidat scoré</div>
                </div>
              )}
            </div>
          </div>

          {/* Camembert — Répartition par profil */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Répartition par profil ML</span>
            </div>
            <div className="card-body">
              {pieData.length > 0 ? (
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%" cy="50%"
                      outerRadius={90}
                      innerRadius={45}
                    >
                      {pieData.map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Legend
                      iconType="circle"
                      iconSize={8}
                      formatter={v => <span style={{ fontSize: 11, color: '#4b5563' }}>{v}</span>}
                    />
                    <Tooltip
                      formatter={v => [v, 'candidats']}
                      contentStyle={{ borderRadius: 8, border: '1px solid #e5e7eb', fontSize: 12 }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="empty-state" style={{ padding: '3rem 0' }}>
                  <div className="empty-state-icon">🗂️</div>
                  <div className="empty-state-title">Aucun profil détecté</div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Bas de page : statuts + top liste ── */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 16 }}>

          {/* Statuts */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Par statut</span>
            </div>
            <div className="card-body" style={{ padding: '12px 20px' }}>
              {statusRows.length > 0 ? statusRows.map(s => (
                <div key={s.key} style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '8px 0', borderBottom: '1px solid var(--gray-200)',
                }}>
                  <span style={{
                    width: 10, height: 10, borderRadius: '50%',
                    background: s.color, flexShrink: 0,
                  }} />
                  <span style={{ flex: 1, fontSize: '0.875rem' }}>{s.label}</span>
                  <span style={{ fontWeight: 700, fontSize: '1rem', color: s.color }}>{s.count}</span>
                  <div style={{
                    width: 60, height: 5, background: 'var(--gray-200)',
                    borderRadius: 99, overflow: 'hidden',
                  }}>
                    <div style={{
                      height: '100%', borderRadius: 99,
                      background: s.color,
                      width: totalStatus ? `${(s.count / totalStatus) * 100}%` : '0%',
                    }} />
                  </div>
                </div>
              )) : (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem', padding: '12px 0' }}>
                  Aucune donnée
                </div>
              )}
            </div>
          </div>

          {/* Top candidats liste */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Meilleurs candidats</span>
            </div>
            {topCandidates.length > 0 ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Candidat</th>
                    <th>Profil</th>
                    <th>Score ML</th>
                  </tr>
                </thead>
                <tbody>
                  {topCandidates.map((c, i) => (
                    <tr key={c.id}>
                      <td>
                        <span style={{
                          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                          width: 24, height: 24, borderRadius: '50%', fontSize: '0.75rem',
                          fontWeight: 700,
                          background: i === 0 ? 'var(--red)' : 'var(--gray-100)',
                          color: i === 0 ? 'white' : 'var(--text-muted)',
                        }}>
                          {i + 1}
                        </span>
                      </td>
                      <td>
                        <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>{c.fullName}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{c.email}</div>
                      </td>
                      <td>
                        <span className="badge badge-gray">{c.profileLabel || '—'}</span>
                      </td>
                      <td style={{ minWidth: 140 }}>
                        <ScoreBar score={c.matchScore} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="card-body empty-state" style={{ padding: '2rem' }}>
                <div className="empty-state-icon">👤</div>
                <div className="empty-state-title">Aucun candidat</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
