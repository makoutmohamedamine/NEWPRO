import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts';
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

/** Recharts passe souvent { payload: point } au clic sur une barre / cellule. */
function unwrapChartData(arg) {
  if (arg && typeof arg === 'object' && arg.payload != null) return arg.payload;
  return arg;
}

function scoreBandMatches(score, bandLabel) {
  const s = toNumber(score);
  const label = String(bandLabel || '').trim();
  if (label === '>=85' || label.startsWith('>=')) return s >= 85;
  if (label === '70-84') return s >= 70 && s < 85;
  if (label === '50-69') return s >= 50 && s < 70;
  if (label === '<50' || label.startsWith('<')) return s < 50;
  return false;
}

function filterByFunnelStatus(candidates, statusKey) {
  return candidates.filter((c) => c.status === statusKey);
}

function filterByScoreBand(candidates, bandLabel) {
  return candidates.filter((c) => {
    if (c.matchScore == null) return false;
    return scoreBandMatches(c.matchScore, bandLabel);
  });
}

function filterByProfileKey(candidates, profileKey) {
  const key = String(profileKey || '').trim();
  return candidates.filter((c) => {
    const tj = String(c.targetJob || '').trim();
    if (key === 'Non classe' || key === 'Non classé') {
      return !tj || tj === 'Non classe' || tj === 'Non classé';
    }
    return tj === key;
  });
}

function filterByJobName(candidates, jobName) {
  const name = String(jobName || '').trim();
  return candidates.filter((c) => String(c.targetJob || '').trim() === name);
}

/* ── Couleurs ────────────────────────────────────────────────────── */
const SCORE_COLORS = ['#15803d', '#2563eb', '#f59e0b', '#dc2626'];
const FUNNEL_COLORS = ['#94a3b8', '#f59e0b', '#3b82f6', '#8b5cf6', '#06b6d4', '#10b981', '#22c55e', '#b42318'];
const PROFILE_COLORS = ['#b42318', '#ea580c', '#d97706', '#2563eb', '#7c3aed', '#0891b2', '#059669', '#be185d'];

/* ── KPI Card ─────────────────────────────────────────────────────── */
function KpiCard({ label, value, sub, color, icon }) {
  return (
    <div style={{
      background: '#fff',
      border: '1px solid var(--gray-200)',
      borderRadius: 12,
      padding: '20px 22px',
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      boxShadow: 'var(--shadow-sm)',
      borderLeft: `4px solid ${color || '#b42318'}`,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 500 }}>{label}</span>
        {icon && <span style={{ fontSize: 22 }}>{icon}</span>}
      </div>
      <div style={{ fontSize: 32, fontWeight: 700, color: color || '#b42318', lineHeight: 1.1 }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{sub}</div>}
    </div>
  );
}

/* ── Chart Card wrapper ───────────────────────────────────────────── */
function ChartCard({ title, children, style, hint }) {
  return (
    <div style={{
      background: '#fff',
      border: '1px solid var(--gray-200)',
      borderRadius: 12,
      boxShadow: 'var(--shadow-sm)',
      overflow: 'hidden',
      ...style,
    }}>
      <div style={{
        padding: '14px 20px',
        borderBottom: '1px solid var(--gray-200)',
        fontWeight: 600,
        fontSize: 14,
        color: 'var(--text)',
      }}>
        {title}
        {hint ? (
          <div style={{ fontSize: 11, fontWeight: 400, color: 'var(--text-muted)', marginTop: 6, lineHeight: 1.4 }}>
            {hint}
          </div>
        ) : null}
      </div>
      <div style={{ padding: '16px 20px' }}>
        {children}
      </div>
    </div>
  );
}

/* ── Tooltip personnalisé ─────────────────────────────────────────── */
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#1d2939',
      color: '#fff',
      padding: '8px 12px',
      borderRadius: 8,
      fontSize: 13,
    }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey}>{p.name || p.dataKey} : <strong>{p.value}</strong></div>
      ))}
    </div>
  );
}

/* ── Badge statut ─────────────────────────────────────────────────── */
const STATUS_COLORS = {
  nouveau: { bg: '#f0f9ff', color: '#0369a1', border: '#bae6fd' },
  prequalifie: { bg: '#f0fdf4', color: '#15803d', border: '#bbf7d0' },
  shortlist: { bg: '#ecfdf5', color: '#0f766e', border: '#a7f3d0' },
  en_cours: { bg: '#fff7ed', color: '#c2410c', border: '#fed7aa' },
  entretien: { bg: '#faf5ff', color: '#7c3aed', border: '#ddd6fe' },
  entretien_rh: { bg: '#faf5ff', color: '#7c3aed', border: '#ddd6fe' },
  entretien_technique: { bg: '#eff6ff', color: '#2563eb', border: '#bfdbfe' },
  validation_manager: { bg: '#faf5ff', color: '#6d28d9', border: '#e9d5ff' },
  finaliste: { bg: '#fdf4ff', color: '#a21caf', border: '#f0abfc' },
  accepte: { bg: '#f0fdf4', color: '#15803d', border: '#bbf7d0' },
  refuse: { bg: '#fff1f2', color: '#be123c', border: '#fecdd3' },
  archive: { bg: '#f4f4f5', color: '#52525b', border: '#e4e4e7' },
};
const STATUS_LABELS = {
  nouveau: 'Nouveau', prequalifie: 'Préqualifié', shortlist: 'Shortlist', en_cours: 'En cours',
  entretien: 'Entretien', entretien_rh: 'Entretien RH', entretien_technique: 'Entretien Tech',
  validation_manager: 'Validation manager', finaliste: 'Finaliste', accepte: 'Accepté', refuse: 'Refusé', archive: 'Archivé',
};
function StatusBadge({ status }) {
  const s = STATUS_COLORS[status] || { bg: '#f2f4f7', color: '#475467', border: '#e4e7ec' };
  return (
    <span style={{
      background: s.bg, color: s.color, border: `1px solid ${s.border}`,
      borderRadius: 20, padding: '2px 10px', fontSize: 11, fontWeight: 600, whiteSpace: 'nowrap',
    }}>
      {STATUS_LABELS[status] || status}
    </span>
  );
}

function CandidateDrillDownModal({ open, onClose, title, subtitle, rows }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      role="presentation"
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 2000,
        background: 'rgba(15, 23, 42, 0.45)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 20,
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="drilldown-title"
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#fff',
          borderRadius: 14,
          maxWidth: 720,
          width: '100%',
          maxHeight: '85vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: 'var(--shadow-lg)',
          border: '1px solid var(--gray-200)',
        }}
      >
        <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--gray-200)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div>
            <h2 id="drilldown-title" style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>{title}</h2>
            {subtitle ? <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--text-muted)' }}>{subtitle}</p> : null}
            <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--text-muted)' }}>
              {rows.length} candidat{rows.length !== 1 ? 's' : ''}
            </p>
          </div>
          <button type="button" className="btn btn-ghost" onClick={onClose} aria-label="Fermer">Fermer</button>
        </div>
        <div style={{ overflow: 'auto', padding: '0 22px 18px' }}>
          {rows.length === 0 ? (
            <div className="empty-state" style={{ padding: '32px 12px', fontSize: 14 }}>Aucun candidat dans cette catégorie.</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, marginTop: 12 }}>
              <thead>
                <tr style={{ background: 'var(--gray-100)' }}>
                  {['Nom', 'Email', 'Poste ciblé', 'Statut', 'Score'].map((h) => (
                    <th key={h} style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)', fontSize: 12 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((c, i) => (
                  <tr key={c.candidatureId || c.id || `${c.email}-${i}`} style={{ borderBottom: '1px solid var(--gray-200)' }}>
                    <td style={{ padding: '10px 12px', fontWeight: 500 }}>{c.fullName || '—'}</td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-muted)', wordBreak: 'break-all' }}>{c.email || '—'}</td>
                    <td style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>{c.targetJob || '—'}</td>
                    <td style={{ padding: '10px 12px' }}><StatusBadge status={c.status} /></td>
                    <td style={{ padding: '10px 12px', fontWeight: 600 }}>
                      {c.matchScore != null ? `${toNumber(c.matchScore).toFixed(0)}%` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div style={{ padding: '12px 22px 18px', borderTop: '1px solid var(--gray-200)' }}>
          <Link to="/candidats" className="btn btn-primary" style={{ display: 'inline-block' }} onClick={onClose}>
            Ouvrir la page Candidats
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [gmailStatus, setGmailStatus] = useState(null);
  const [gmailSyncing, setGmailSyncing] = useState(false);
  const [gmailMessage, setGmailMessage] = useState('');
  const [lastRefreshed, setLastRefreshed] = useState(null);
  const [syncingDashboard, setSyncingDashboard] = useState(false);
  const [drillDown, setDrillDown] = useState(null);

  const openDrillDown = useCallback((title, subtitle, rows) => {
    setDrillDown({ title, subtitle, rows: rows || [] });
  }, []);

  const closeDrillDown = useCallback(() => setDrillDown(null), []);

  const loadGmailConnection = useCallback(async () => {
    try {
      const gmailRes = await getGmailStatus();
      const statusData = gmailRes?.data || null;
      if (statusData?.connection?.status === 'ok') { setGmailStatus(statusData); return statusData; }
    } catch (_) {}
    try {
      const debugRes = await getGmailDebug();
      const d = debugRes?.data || {};
      const normalized = { connection: d.connection || { status: 'error' }, syncHistory: [], emailLogs: [], totalEmailsProcessed: toNumber(d.already_processed), totalSyncs: 0 };
      setGmailStatus(normalized); return normalized;
    } catch (_) {
      const dc = { connection: { status: 'error' } }; setGmailStatus(dc); return dc;
    }
  }, []);

  const gmailConnected = gmailStatus?.connection?.status === 'ok' && Boolean(gmailStatus?.connection?.mailbox);

  const loadDashboard = useCallback(async (silent = false) => {
    setError('');
    if (!silent) setLoading(true);
    setSyncingDashboard(true);
    try {
      const [dashRes] = await Promise.all([getDashboard(), loadGmailConnection()]);
      setDashboard(dashRes.data || {});
      setLastRefreshed(new Date());
    } catch (err) {
      if (!silent) setError(err?.response?.data?.error || 'Impossible de charger le dashboard.');
    } finally {
      if (!silent) setLoading(false);
      setSyncingDashboard(false);
    }
  }, [loadGmailConnection]);

  useEffect(() => {
    loadDashboard();
    const interval = setInterval(() => loadDashboard(true), 60000);
    const onFocus = () => loadDashboard(true);
    window.addEventListener('focus', onFocus);
    return () => {
      clearInterval(interval);
      window.removeEventListener('focus', onFocus);
    };
  }, [loadDashboard]);

  const handleGmailSync = async () => {
    setGmailSyncing(true); setGmailMessage('');
    try {
      const res = await triggerGmailSync();
      const report = res.data || {};
      setGmailMessage(
        report.success
          ? `Sync Gmail terminee: ${toNumber(report.cvsCreated)} CV crees, ${toNumber(report.cvsFound)} trouves.`
          : report.errors?.[0] || 'Echec de la synchronisation Gmail.'
      );
      await loadGmailConnection(); await loadDashboard();
    } catch (err) {
      setGmailMessage(err?.response?.data?.error || err?.response?.data?.detail || 'Echec de la synchronisation Gmail.');
    } finally { setGmailSyncing(false); }
  };

  const stats = dashboard?.stats || {};
  const topCandidates = dashboard?.topCandidates || [];
  const jobsOverview = dashboard?.jobsOverview || [];
  const slaAlerts = dashboard?.slaAlerts || [];
  const funnel = useMemo(
    () => (Array.isArray(dashboard?.funnel) ? dashboard.funnel : []),
    [dashboard]
  );
  const scoreDistribution = useMemo(
    () => (Array.isArray(dashboard?.scoreDistribution) ? dashboard.scoreDistribution : []),
    [dashboard]
  );
  const profileDistribution = useMemo(() => {
    const p = dashboard?.profileDistribution;
    return p && typeof p === 'object' ? p : {};
  }, [dashboard]);
  const recentCandidates = dashboard?.recentCandidates || [];
  const allCandidates = useMemo(
    () => (Array.isArray(dashboard?.candidates) ? dashboard.candidates : []),
    [dashboard]
  );

  const funnelData = useMemo(
    () => funnel.filter((f) => f.count > 0).map((f, i) => ({
      name: f.label,
      statusKey: f.key,
      value: f.count,
      fill: FUNNEL_COLORS[i % FUNNEL_COLORS.length],
    })),
    [funnel]
  );

  const scoreData = useMemo(
    () => scoreDistribution.map((s, i) => ({
      name: s.label,
      bandKey: s.label,
      value: s.count,
      fill: SCORE_COLORS[i % SCORE_COLORS.length],
    })),
    [scoreDistribution]
  );

  const profileData = useMemo(
    () => Object.entries(profileDistribution)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([fullKey, count], i) => ({
        name: fullKey.length > 18 ? `${fullKey.slice(0, 17)}…` : fullKey,
        profileKey: fullKey,
        value: count,
        fill: PROFILE_COLORS[i % PROFILE_COLORS.length],
      })),
    [profileDistribution]
  );

  const onFunnelBarClick = useCallback((raw, index) => {
    const row = unwrapChartData(raw);
    const d = row?.statusKey ? row : funnelData[index];
    if (!d?.statusKey) return;
    const rows = filterByFunnelStatus(allCandidates, d.statusKey);
    openDrillDown('Candidats par étape du pipeline', d.name, rows);
  }, [allCandidates, funnelData, openDrillDown]);

  const onScoreBandClick = useCallback((raw, index) => {
    const row = unwrapChartData(raw);
    const d = row?.bandKey ? row : scoreData[index];
    const band = d?.bandKey || d?.name;
    if (!band) return;
    const rows = filterByScoreBand(allCandidates, band);
    openDrillDown('Candidats par tranche de score', `Tranche : ${band}`, rows);
  }, [allCandidates, scoreData, openDrillDown]);

  const onProfileBarClick = useCallback((raw, index) => {
    const row = unwrapChartData(raw);
    const d = row?.profileKey ? row : profileData[index];
    if (!d?.profileKey) return;
    const rows = filterByProfileKey(allCandidates, d.profileKey);
    openDrillDown('Candidats par profil de poste', d.profileKey, rows);
  }, [allCandidates, profileData, openDrillDown]);

  const onJobRowClick = useCallback((job) => {
    if (!job?.name) return;
    const rows = filterByJobName(allCandidates, job.name);
    openDrillDown('Candidats pour ce poste', job.name, rows);
  }, [allCandidates, openDrillDown]);

  const totalScored = scoreData.reduce((sum, s) => sum + s.value, 0);

  const quickLinks = useMemo(() => [
    { to: '/dossiers-cv', title: 'Dossiers CV', desc: 'CV classés automatiquement', icon: '📁', color: '#b42318' },
    { to: '/candidats', title: 'Candidats', desc: 'Suivi et statuts', icon: '👥', color: '#ea580c' },
    { to: '/postes', title: 'Fiches de poste', desc: 'Gérer les offres', icon: '📋', color: '#2563eb' },
    { to: '/analyse-ia', title: 'Analyse IA', desc: 'Scoring avancé', icon: '🤖', color: '#7c3aed' },
    { to: '/utilisateurs', title: 'Utilisateurs', desc: 'Gérer les comptes', icon: '⚙️', color: '#475467' },
  ], []);

  return (
    <>
      <div className="page-header dashboard-page-header">
        <span className="page-header-title">TalentMatch IA</span>
        <div className="page-header-right" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span className={`dashboard-sync-pill ${syncingDashboard ? 'is-syncing' : 'is-synced'}`}>
            <span />
            {syncingDashboard ? 'Synchronisation...' : 'Synchronisé'}
          </span>
          {lastRefreshed && (
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              Mis à jour {lastRefreshed.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
          <button className="btn btn-ghost" type="button" onClick={() => loadDashboard(false)}>Actualiser</button>
        </div>
      </div>

      <div className="page-content dashboard-page-content">
        {loading ? (
          <div className="empty-state"><div className="spinner" style={{ margin: '0 auto 12px' }} />Chargement du dashboard...</div>
        ) : error ? (
          <div className="alert alert-error">{error}</div>
        ) : (
          <>
            {/* ── Hero banner ──────────────────────────────────────── */}
            <div style={{
              background: 'linear-gradient(135deg, #b42318 0%, #7a1c14 100%)',
              borderRadius: 14,
              padding: '28px 32px',
              color: '#fff',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 20,
            }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 1, opacity: 0.75, marginBottom: 6 }}>Pilotage global</div>
                <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0, lineHeight: 1.2 }}>Tableau de bord recrutement</h1>
                <p style={{ margin: '6px 0 0', opacity: 0.8, fontSize: 13 }}>Vue d'ensemble en temps réel de toute votre activité RH</p>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {[
                  { v: toNumber(stats.totalCandidates), l: 'Candidats' },
                  { v: toNumber(stats.openJobs), l: 'Postes ouverts' },
                  { v: toNumber(stats.interviewsCount), l: 'Entretiens' },
                  { v: toNumber(stats.overdueActions), l: 'En retard' },
                ].map((item) => (
                  <div key={item.l} style={{ background: 'rgba(255,255,255,0.15)', borderRadius: 10, padding: '12px 16px', textAlign: 'center', minWidth: 80 }}>
                    <div style={{ fontSize: 26, fontWeight: 700 }}>{item.v}</div>
                    <div style={{ fontSize: 11, opacity: 0.85 }}>{item.l}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* ── KPI Cards ─────────────────────────────────────────── */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 14 }}>
              <KpiCard label="Total candidatures" value={toNumber(stats.totalApplications)} sub="Toutes candidatures" color="#b42318" icon="📊" />
              <KpiCard label="Nouveaux" value={toNumber(stats.newCandidates)} sub="À qualifier" color="#ea580c" icon="🆕" />
              <KpiCard label="Qualifiés (≥70%)" value={toNumber(stats.qualifiedCandidates)} sub="Score ≥ 70%" color="#15803d" icon="✅" />
              <KpiCard label="Score moyen" value={`${toNumber(stats.averageScore).toFixed(1)}%`} sub={`Meilleur: ${toNumber(stats.bestScore).toFixed(1)}%`} color="#2563eb" icon="🎯" />
              <KpiCard label="Acceptés" value={toNumber(stats.acceptedCandidates)} sub="Offre acceptée" color="#059669" icon="🏆" />
              <KpiCard label="Délai moyen" value={`${toNumber(stats.processingDelayHours).toFixed(0)}h`} sub="Traitement moyen" color="#7c3aed" icon="⏱️" />
            </div>

            {/* ── Graphiques ligne 1 : Funnel + Score distribution ─── */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

              {/* Funnel recrutement */}
              <ChartCard title="Entonnoir de recrutement" hint="Cliquez sur une barre pour afficher la liste des candidats à cette étape.">
                {funnelData.length === 0 ? (
                  <div className="empty-state" style={{ padding: '32px 0', fontSize: 13 }}>Aucune donnée de pipeline.</div>
                ) : (
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={funnelData} layout="vertical" margin={{ left: 10, right: 20, top: 4, bottom: 4 }}>
                      <XAxis type="number" tick={{ fontSize: 11, fill: '#667085' }} />
                      <YAxis type="category" dataKey="name" width={110} tick={{ fontSize: 11, fill: '#475467' }} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="value" name="Candidats" radius={[0, 6, 6, 0]} cursor="pointer" onClick={onFunnelBarClick}>
                        {funnelData.map((entry, index) => (
                          <Cell key={index} fill={entry.fill} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </ChartCard>

              {/* Distribution des scores */}
              <ChartCard title="Répartition des scores" hint="Cliquez sur le graphique ou sur une ligne de la légende pour afficher les candidats de cette tranche.">
                {totalScored === 0 ? (
                  <div className="empty-state" style={{ padding: '32px 0', fontSize: 13 }}>Aucun score disponible.</div>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <ResponsiveContainer width="55%" height={220}>
                      <PieChart>
                        <Pie
                          data={scoreData}
                          cx="50%" cy="50%"
                          innerRadius={55}
                          outerRadius={90}
                          paddingAngle={3}
                          dataKey="value"
                          cursor="pointer"
                          onClick={onScoreBandClick}
                        >
                          {scoreData.map((entry, index) => (
                            <Cell key={index} fill={entry.fill} />
                          ))}
                        </Pie>
                        <Tooltip formatter={(v) => [`${v} candidat(s)`, '']} />
                      </PieChart>
                    </ResponsiveContainer>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1 }}>
                      {scoreData.map((s, i) => (
                        <button
                          key={s.name}
                          type="button"
                          onClick={() => onScoreBandClick(s, i)}
                          style={{
                            display: 'flex', alignItems: 'center', gap: 8,
                            background: 'none', border: 'none', padding: '6px 4px', margin: 0,
                            width: '100%', textAlign: 'left', cursor: 'pointer', borderRadius: 8,
                          }}
                          onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--gray-100)'; }}
                          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                        >
                          <div style={{ width: 12, height: 12, borderRadius: 3, background: s.fill, flexShrink: 0 }} />
                          <div style={{ flex: 1, fontSize: 12, color: 'var(--text-muted)' }}>{s.name}</div>
                          <div style={{ fontWeight: 600, fontSize: 13 }}>{s.value}</div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)', width: 36, textAlign: 'right' }}>
                            {totalScored > 0 ? `${Math.round((s.value / totalScored) * 100)}%` : ''}
                          </div>
                        </button>
                      ))}
                      <div style={{ marginTop: 6, paddingTop: 8, borderTop: '1px solid var(--gray-200)', fontSize: 12, color: 'var(--text-muted)' }}>
                        {totalScored} candidat(s) scoré(s)
                      </div>
                    </div>
                  </div>
                )}
              </ChartCard>
            </div>

            {/* ── Graphiques ligne 2 : Profils + Postes ─────────────── */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

              {/* Candidats par profil */}
              <ChartCard title="Candidats par profil de poste" hint="Cliquez sur une barre pour afficher les candidats rattachés à ce profil.">
                {profileData.length === 0 ? (
                  <div className="empty-state" style={{ padding: '32px 0', fontSize: 13 }}>Aucun profil configuré.</div>
                ) : (
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={profileData} margin={{ left: 0, right: 10, top: 4, bottom: 40 }}>
                      <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#667085' }} angle={-30} textAnchor="end" interval={0} />
                      <YAxis tick={{ fontSize: 11, fill: '#667085' }} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="value" name="Candidats" radius={[6, 6, 0, 0]} cursor="pointer" onClick={onProfileBarClick}>
                        {profileData.map((entry, index) => (
                          <Cell key={index} fill={entry.fill} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </ChartCard>

              {/* Postes suivis */}
              <ChartCard title="Postes suivis" hint="Cliquez sur une ligne du tableau pour afficher les candidats sur ce poste.">
                {jobsOverview.length === 0 ? (
                  <div className="empty-state" style={{ padding: '32px 0', fontSize: 13 }}>Aucun poste configuré.</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 0, maxHeight: 240, overflowY: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                      <thead>
                        <tr style={{ background: 'var(--gray-100)' }}>
                          {['Poste', 'Candid.', 'Qualif.', 'Moy.'].map((h) => (
                            <th key={h} style={{ padding: '8px 10px', textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)', fontSize: 12 }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {jobsOverview.slice(0, 8).map((job, i) => (
                          <tr
                            key={job.id}
                            onClick={() => onJobRowClick(job)}
                            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onJobRowClick(job); } }}
                            role="button"
                            tabIndex={0}
                            style={{
                              borderBottom: '1px solid var(--gray-200)',
                              background: i % 2 === 0 ? '#fff' : 'var(--gray-100)',
                              cursor: 'pointer',
                            }}
                          >
                            <td style={{ padding: '8px 10px', fontWeight: 500, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{job.name}</td>
                            <td style={{ padding: '8px 10px', textAlign: 'center' }}>{toNumber(job.candidateCount)}</td>
                            <td style={{ padding: '8px 10px', textAlign: 'center' }}>
                              <span style={{ color: '#15803d', fontWeight: 600 }}>{toNumber(job.qualifiedCount)}</span>
                            </td>
                            <td style={{ padding: '8px 10px', textAlign: 'center', color: '#2563eb', fontWeight: 600 }}>
                              {toNumber(job.avgScore).toFixed(0)}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </ChartCard>
            </div>

            {/* ── Top candidats + Alertes SLA ───────────────────────── */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

              {/* Top candidats */}
              <ChartCard title="🏆 Top candidats (meilleurs scores)">
                {topCandidates.length === 0 ? (
                  <div className="empty-state" style={{ padding: '24px 0', fontSize: 13 }}>Aucun candidat scoré.</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {topCandidates.map((c, i) => {
                      const score = toNumber(c.matchScore);
                      const barColor = score >= 85 ? '#15803d' : score >= 70 ? '#2563eb' : '#f59e0b';
                      return (
                        <div key={c.id || i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <div style={{
                            width: 28, height: 28, borderRadius: '50%', background: '#f2f4f7',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontWeight: 700, fontSize: 13, color: '#475467', flexShrink: 0,
                          }}>{i + 1}</div>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontWeight: 600, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {c.fullName || 'Candidat'}
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                              {c.targetJob || 'Sans poste'}
                            </div>
                            <div style={{ marginTop: 4, height: 4, borderRadius: 4, background: 'var(--gray-200)', overflow: 'hidden' }}>
                              <div style={{ height: '100%', width: `${score}%`, background: barColor, borderRadius: 4, transition: 'width 0.6s ease' }} />
                            </div>
                          </div>
                          <div style={{ fontWeight: 700, fontSize: 14, color: barColor, flexShrink: 0, minWidth: 44, textAlign: 'right' }}>
                            {score.toFixed(0)}%
                          </div>
                          <StatusBadge status={c.status} />
                        </div>
                      );
                    })}
                  </div>
                )}
              </ChartCard>

              {/* Alertes SLA */}
              <ChartCard title="⚡ Alertes — Candidats à fort potentiel non traités">
                {slaAlerts.length === 0 ? (
                  <div className="empty-state" style={{ padding: '24px 0', fontSize: 13 }}>Aucune alerte critique.</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {slaAlerts.map((item, i) => (
                      <div key={item.id || i} style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '10px 12px', background: '#fff8f0', borderRadius: 8,
                        border: '1px solid #fed7aa', gap: 12,
                      }}>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontWeight: 600, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {item.fullName || 'Candidat'}
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{item.targetJob || 'Sans poste'}</div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                          <StatusBadge status={item.status} />
                          <span style={{
                            background: '#fef3c7', color: '#92400e', border: '1px solid #fde68a',
                            borderRadius: 20, padding: '2px 10px', fontSize: 12, fontWeight: 700,
                          }}>
                            {toNumber(item.matchScore).toFixed(0)}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </ChartCard>
            </div>

            {/* ── Candidats récents ─────────────────────────────────── */}
            {recentCandidates.length > 0 && (
              <ChartCard title="👤 Candidats récents">
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                    <thead>
                      <tr style={{ background: 'var(--gray-100)' }}>
                        {['Nom', 'Poste ciblé', 'Statut', 'Score', 'Source'].map((h) => (
                          <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)', fontSize: 12 }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {recentCandidates.map((c, i) => (
                        <tr key={c.id || i} style={{ borderBottom: '1px solid var(--gray-200)' }}>
                          <td style={{ padding: '9px 12px', fontWeight: 500 }}>{c.fullName || '—'}</td>
                          <td style={{ padding: '9px 12px', color: 'var(--text-muted)' }}>{c.targetJob || '—'}</td>
                          <td style={{ padding: '9px 12px' }}><StatusBadge status={c.status} /></td>
                          <td style={{ padding: '9px 12px', fontWeight: 600, color: toNumber(c.matchScore) >= 70 ? '#15803d' : '#667085' }}>
                            {c.matchScore != null ? `${toNumber(c.matchScore).toFixed(0)}%` : '—'}
                          </td>
                          <td style={{ padding: '9px 12px', color: 'var(--text-muted)', fontSize: 12 }}>{c.source || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </ChartCard>
            )}

            {/* ── Accès rapide ──────────────────────────────────────── */}
            <div>
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 12, color: 'var(--text-muted)' }}>Accès rapide</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
                {quickLinks.map((item) => (
                  <Link key={item.to} to={item.to} style={{
                    background: '#fff', border: '1px solid var(--gray-200)', borderRadius: 12,
                    padding: '16px', display: 'flex', flexDirection: 'column', gap: 6,
                    boxShadow: 'var(--shadow-sm)', textDecoration: 'none', color: 'inherit',
                    transition: 'box-shadow 0.2s, border-color 0.2s',
                    borderTop: `3px solid ${item.color}`,
                  }}
                    onMouseEnter={(e) => { e.currentTarget.style.boxShadow = 'var(--shadow-md)'; e.currentTarget.style.borderColor = item.color; }}
                    onMouseLeave={(e) => { e.currentTarget.style.boxShadow = 'var(--shadow-sm)'; e.currentTarget.style.borderColor = 'var(--gray-200)'; }}
                  >
                    <div style={{ fontSize: 22 }}>{item.icon}</div>
                    <div style={{ fontWeight: 600, fontSize: 13 }}>{item.title}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{item.desc}</div>
                  </Link>
                ))}
              </div>
            </div>

            {/* ── Outils : CV Upload + Sync ─────────────────────────── */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <CVUpload onUploadSuccess={loadDashboard} />
              <div style={{ display: 'grid', gap: 16 }}>
                <OutlookSync onSyncSuccess={loadDashboard} />
                <div className="card">
                  <div className="card-header">
                    <span className="card-title">Synchronisation Gmail</span>
                    <span className={`badge ${gmailConnected ? 'badge-green' : 'badge-gray'}`}>
                      {gmailConnected ? 'Connecté' : 'Non connecté'}
                    </span>
                  </div>
                  <div className="card-body" style={{ display: 'grid', gap: 12 }}>
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                      Boite: {gmailStatus?.connection?.mailbox || 'non configurée'}
                    </div>
                    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                      <button className="btn btn-primary" type="button" onClick={handleGmailSync} disabled={gmailSyncing}>
                        {gmailSyncing ? 'Synchronisation...' : 'Lancer sync Gmail'}
                      </button>
                      <button className="btn btn-ghost" type="button" onClick={loadDashboard}>Rafraîchir indicateurs</button>
                    </div>
                    {gmailMessage && (
                      <div className={`alert ${gmailMessage.toLowerCase().includes('echec') ? 'alert-error' : 'alert-success'}`}>
                        {gmailMessage}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
            <CandidateDrillDownModal
              open={Boolean(drillDown)}
              onClose={closeDrillDown}
              title={drillDown?.title || ''}
              subtitle={drillDown?.subtitle || ''}
              rows={drillDown?.rows || []}
            />
          </>
        )}
      </div>
    </>
  );
}
