import { useState, useEffect, useCallback } from 'react';
import { triggerGmailSync, getGmailStatus, getGmailDebug } from '../api/api';

const STATUS_META = {
  processed: { badge: 'badge-green',  label: 'Traité' },
  duplicate:  { badge: 'badge-yellow', label: 'Doublon' },
  error:      { badge: 'badge-red',    label: 'Erreur' },
  no_cv:      { badge: 'badge-gray',   label: 'Sans CV' },
};

const CMD = 'python manage.py gmail_auth';

// ── Icône Gmail SVG ────────────────────────────────────────────────────────────
const GmailIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
    <path d="M20 4H4C2.9 4 2 4.9 2 6v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2z" fill="#EA4335" opacity=".2"/>
    <path d="M2 6l10 7 10-7" stroke="#EA4335" strokeWidth="1.5" strokeLinecap="round"/>
    <path d="M20 4H4L12 11l8-7z" fill="#EA4335"/>
  </svg>
);

export default function GmailSync() {
  const [status, setStatus]       = useState(null);
  const [syncing, setSyncing]     = useState(false);
  const [report, setReport]       = useState(null);
  const [loading, setLoading]     = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [debug, setDebug]         = useState(null);
  const [debugging, setDebugging] = useState(false);
  const [copied, setCopied]       = useState(false);

  const handleDebug = async () => {
    setDebugging(true);
    setDebug(null);
    try {
      const res = await getGmailDebug();
      setDebug(res.data);
    } catch (err) {
      setDebug({ error: err.response?.data?.error || 'Erreur réseau' });
    } finally {
      setDebugging(false);
    }
  };

  const loadStatus = useCallback(async (showRefreshing = false) => {
    if (showRefreshing) setRefreshing(true);
    try {
      const res = await getGmailStatus();
      setStatus(res.data);
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  const handleSync = async () => {
    setSyncing(true);
    setReport(null);
    try {
      const res = await triggerGmailSync();
      setReport(res.data);
      await loadStatus();
    } catch (err) {
      setReport({
        success: false,
        errors: [err.response?.data?.error || 'Erreur inconnue'],
        cvsCreated: 0, emailsScanned: 0, cvsFound: 0, cvsError: 1,
      });
    } finally {
      setSyncing(false);
    }
  };

  const copyCmd = () => {
    navigator.clipboard.writeText(CMD).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const conn          = status?.connection;
  const isConnected   = conn?.status === 'ok';
  const notConfigured = conn?.status === 'not_configured';

  return (
    <>
      {/* Header */}
      <div className="page-header">
        <span className="page-header-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <GmailIcon /> Gmail Sync
        </span>
        <div className="page-header-right">
          {!loading && (
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              background: isConnected ? '#dcfce7' : '#fee2e2',
              color: isConnected ? '#166534' : '#991b1b',
              borderRadius: 99, padding: '3px 12px', fontSize: '0.78rem', fontWeight: 600,
            }}>
              <span style={{
                width: 7, height: 7, borderRadius: '50%',
                background: isConnected ? '#16a34a' : '#dc2626',
                display: 'inline-block',
              }} />
              {isConnected
                ? `Connecté — ${conn.mailbox}`
                : notConfigured
                ? 'Autorisation requise'
                : 'Erreur de connexion'}
            </span>
          )}
          {/* Bouton Vérifier à nouveau — visible si pas connecté */}
          {!loading && !isConnected && (
            <button
              className="btn"
              onClick={() => loadStatus(true)}
              disabled={refreshing}
              style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            >
              {refreshing
                ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Vérification…</>
                : '↻ Vérifier à nouveau'}
            </button>
          )}
          <button
            className="btn"
            onClick={handleDebug}
            disabled={debugging}
            style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
          >
            {debugging ? <><span className="spinner" style={{ width: 14, height: 14 }} /> …</> : '🔍 Diagnostiquer'}
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSync}
            disabled={syncing || !isConnected}
            title={!isConnected ? 'Autorisez d\'abord Gmail en exécutant la commande ci-dessous' : ''}
            style={{ background: '#EA4335', borderColor: '#EA4335' }}
          >
            {syncing
              ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Synchro…</>
              : '⟳ Lancer la synchro'}
          </button>
        </div>
      </div>

      <div className="page-content">

        {/* ── Bloc : autorisation requise ── */}
        {!loading && notConfigured && (
          <div style={{
            background: 'linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)',
            border: '1.5px solid #f59e0b',
            borderRadius: 12,
            padding: '20px 24px',
            marginBottom: 24,
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
              <div style={{
                fontSize: 28, lineHeight: 1,
                background: '#fde68a', borderRadius: 10,
                padding: '8px 12px', flexShrink: 0,
              }}>
                🔑
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700, color: '#78350f', fontSize: '1rem', marginBottom: 6 }}>
                  Autorisation Gmail requise
                </div>
                <p style={{ fontSize: '0.875rem', color: '#92400e', margin: '0 0 16px', lineHeight: 1.6 }}>
                  L'application n'a pas encore accès à votre compte Gmail.
                  Vous devez exécuter cette commande <strong>une seule fois</strong> dans le terminal
                  du backend (dans le dossier <code style={{ background: '#fde68a', padding: '1px 6px', borderRadius: 4 }}>backend/</code>) :
                </p>

                {/* Commande à copier */}
                <div style={{
                  background: '#1a1a2e', borderRadius: 8, overflow: 'hidden',
                  display: 'flex', alignItems: 'center',
                  border: '1px solid #374151',
                  marginBottom: 16,
                }}>
                  <code style={{
                    flex: 1, padding: '12px 16px',
                    color: '#4ade80', fontFamily: 'monospace',
                    fontSize: '0.9rem', letterSpacing: '0.02em',
                    userSelect: 'all',
                  }}>
                    {CMD}
                  </code>
                  <button
                    onClick={copyCmd}
                    style={{
                      background: copied ? '#16a34a' : '#374151',
                      border: 'none', color: '#fff',
                      padding: '12px 16px', cursor: 'pointer',
                      fontSize: '0.82rem', fontWeight: 600,
                      transition: 'background 0.2s',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {copied ? '✓ Copié !' : '📋 Copier'}
                  </button>
                </div>

                {/* Étapes */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {[
                    'Ouvrez un terminal dans le dossier backend/',
                    'Collez et exécutez la commande ci-dessus',
                    'Un navigateur s\'ouvrira → connectez-vous à Google et autorisez l\'accès',
                    'Le fichier token.json sera créé automatiquement',
                    'Revenez ici et cliquez « ↻ Vérifier à nouveau »',
                  ].map((step, i) => (
                    <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', fontSize: '0.83rem', color: '#78350f' }}>
                      <span style={{
                        width: 20, height: 20, borderRadius: '50%',
                        background: '#f59e0b', color: '#fff',
                        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                        fontWeight: 700, fontSize: '0.72rem', flexShrink: 0, marginTop: 1,
                      }}>
                        {i + 1}
                      </span>
                      {step}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Panneau de diagnostic */}
        {debug && (
          <div className="card card-body" style={{ marginBottom: 20, fontSize: '0.83rem' }}>
            <div style={{ fontWeight: 700, marginBottom: 10 }}>Résultat du diagnostic</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 10 }}>
              {[
                { label: 'client_secret.json', ok: debug.secret_file_exists },
                { label: 'token.json',         ok: debug.token_file_exists },
                { label: 'Connexion Gmail',    ok: debug.connection?.status === 'ok' },
                { label: 'Emails CV trouvés',  value: debug.emails_found ?? 0 },
                { label: 'Déjà traités en DB', value: debug.already_processed ?? 0 },
              ].map(({ label, ok, value }) => (
                <div key={label} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span style={{ color: ok === false ? '#dc2626' : ok === true ? '#16a34a' : '#6b7280', fontWeight: 700 }}>
                    {ok === true ? '✓' : ok === false ? '✗' : '→'}
                  </span>
                  <span style={{ color: 'var(--text-muted)' }}>{label} :</span>
                  <span style={{ fontWeight: 600 }}>
                    {ok === true ? 'OK' : ok === false ? 'MANQUANT' : value}
                  </span>
                </div>
              ))}
            </div>
            {debug.connection?.mailbox && (
              <div style={{ color: '#16a34a', marginBottom: 6 }}>Boite : {debug.connection.mailbox}</div>
            )}
            {debug.sample_emails?.length > 0 && (
              <div>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>Emails CV détectés :</div>
                {debug.sample_emails.map((e, i) => (
                  <div key={i} style={{ padding: '3px 0', color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
                    <span style={{ color: 'var(--text)', fontWeight: 500 }}>{e.from?.split('<')[0] || e.from}</span>
                    {' — '}{e.subject}
                  </div>
                ))}
              </div>
            )}
            {debug.error && (
              <div style={{ color: '#dc2626', marginTop: 6 }}>Erreur : {debug.error}</div>
            )}
          </div>
        )}

        {/* Erreur connexion */}
        {!loading && conn?.status === 'error' && (
          <div className="alert alert-error" style={{ marginBottom: 20 }}>
            <span>⚠</span>
            <div>
              <strong>Connexion Gmail impossible :</strong> {conn.error}
            </div>
          </div>
        )}

        {/* Boite connectée */}
        {isConnected && (
          <div className="alert alert-info" style={{ marginBottom: 20 }}>
            <GmailIcon />
            <span>
              Boite surveillée : <strong>{conn.mailbox}</strong>
              {conn.messagesTotal != null && (
                <span style={{ color: 'var(--text-muted)', marginLeft: 8, fontSize: '0.82rem' }}>
                  ({conn.messagesTotal.toLocaleString('fr-FR')} emails au total)
                </span>
              )}
            </span>
          </div>
        )}

        {/* Rapport de synchro */}
        {report && (
          <div
            className={`alert ${report.success ? 'alert-success' : 'alert-error'}`}
            style={{ marginBottom: 20, flexDirection: 'column', alignItems: 'stretch' }}
          >
            <div style={{ fontWeight: 700, marginBottom: 12 }}>
              {report.success ? '✓ Synchronisation Gmail terminée' : '⚠ Synchronisation avec erreurs'}
            </div>
            <div className="kpi-grid" style={{ margin: 0 }}>
              {[
                { label: 'Emails analysés', value: report.emailsScanned ?? 0, color: '#1a1a1a' },
                { label: 'CVs trouvés',     value: report.cvsFound ?? 0,      color: '#1d4ed8' },
                { label: 'CVs importés',    value: report.cvsCreated ?? 0,    color: '#16a34a' },
                { label: 'Erreurs',         value: report.cvsError ?? 0,      color: '#dc2626' },
              ].map(s => (
                <div key={s.label} className="kpi-card" style={{ '--kpi-color': s.color }}>
                  <div className="kpi-value">{s.value}</div>
                  <div className="kpi-label">{s.label}</div>
                </div>
              ))}
            </div>
            {report.errors?.length > 0 && (
              <ul style={{ margin: '12px 0 0', paddingLeft: 18, fontSize: '0.83rem' }}>
                {report.errors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            )}
          </div>
        )}

        {/* KPIs globaux */}
        {status && (
          <div className="kpi-grid" style={{ marginBottom: 24 }}>
            {[
              { value: status.totalEmailsProcessed ?? 0, label: 'Emails traités',   color: '#EA4335' },
              { value: status.totalSyncs ?? 0,           label: 'Synchronisations', color: '#1a1a1a' },
              {
                value: status.syncHistory?.reduce((s, h) => s + (h.cvsCreated || 0), 0) ?? 0,
                label: 'CVs importés', color: '#16a34a',
              },
              {
                value: status.syncHistory?.reduce((s, h) => s + (h.cvsError || 0), 0) ?? 0,
                label: 'Erreurs totales', color: '#dc2626',
              },
            ].map(k => (
              <div key={k.label} className="kpi-card" style={{ '--kpi-color': k.color }}>
                <div className="kpi-value">{k.value}</div>
                <div className="kpi-label">{k.label}</div>
              </div>
            ))}
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

          {/* Historique synchros */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Historique des synchronisations</span>
            </div>
            {status?.syncHistory?.length > 0 ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Emails</th>
                    <th>Importés</th>
                    <th>Erreurs</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>
                  {status.syncHistory.map((s, i) => (
                    <tr key={i}>
                      <td style={{ fontSize: '0.8rem' }}>
                        {new Date(s.startedAt).toLocaleString('fr-FR', {
                          day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
                        })}
                      </td>
                      <td>{s.emailsScanned}</td>
                      <td style={{ fontWeight: 700, color: '#16a34a' }}>{s.cvsCreated}</td>
                      <td style={{ color: s.cvsError > 0 ? '#dc2626' : 'var(--gray-400)' }}>
                        {s.cvsError}
                      </td>
                      <td><span className="badge badge-gray">{s.triggeredBy}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="empty-state card-body" style={{ padding: '2rem' }}>
                <div className="empty-state-icon">📋</div>
                <div className="empty-state-title">Aucune synchro effectuée</div>
              </div>
            )}
          </div>

          {/* Journal des emails */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">
                Journal des emails ({status?.totalEmailsProcessed ?? 0})
              </span>
            </div>
            {status?.emailLogs?.length > 0 ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Statut</th>
                    <th>Expéditeur</th>
                    <th>Fichier</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {status.emailLogs.map((log, i) => {
                    const m = STATUS_META[log.status] || STATUS_META.error;
                    return (
                      <tr key={i}>
                        <td><span className={`badge ${m.badge}`}>{m.label}</span></td>
                        <td>
                          <div style={{ fontSize: '0.83rem', fontWeight: 500 }}>
                            {log.senderName || log.senderEmail}
                          </div>
                          {log.candidatName && (
                            <div style={{ fontSize: '0.72rem', color: '#EA4335' }}>
                              → {log.candidatName}
                            </div>
                          )}
                        </td>
                        <td style={{
                          fontSize: '0.78rem', color: 'var(--text-muted)',
                          maxWidth: 140, overflow: 'hidden',
                          textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}>
                          {log.filename || log.subject || '—'}
                        </td>
                        <td style={{ fontSize: '0.75rem', color: 'var(--gray-400)', whiteSpace: 'nowrap' }}>
                          {new Date(log.createdAt).toLocaleDateString('fr-FR')}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <div className="empty-state card-body" style={{ padding: '2rem' }}>
                <div className="empty-state-icon">✉</div>
                <div className="empty-state-title">Aucun email traité</div>
              </div>
            )}
          </div>
        </div>

        {loading && (
          <div className="empty-state">
            <div className="spinner" style={{ margin: '0 auto 12px' }} />
            Chargement du statut Gmail…
          </div>
        )}
      </div>
    </>
  );
}
