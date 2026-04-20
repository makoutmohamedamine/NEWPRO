import { useState, useEffect, useCallback } from 'react';
import { triggerOutlookSync, getOutlookStatus } from '../api/api';

const STATUS_META = {
  processed: { badge: 'badge-green',  label: 'Traité' },
  duplicate:  { badge: 'badge-yellow', label: 'Doublon' },
  error:      { badge: 'badge-red',    label: 'Erreur' },
  no_cv:      { badge: 'badge-gray',   label: 'Sans CV' },
};

export default function OutlookSync() {
  const [status, setStatus]     = useState(null);
  const [syncing, setSyncing]   = useState(false);
  const [report, setReport]     = useState(null);
  const [loading, setLoading]   = useState(true);

  const loadStatus = useCallback(async () => {
    try {
      const res = await getOutlookStatus();
      setStatus(res.data);
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  const handleSync = async () => {
    setSyncing(true);
    setReport(null);
    try {
      const res = await triggerOutlookSync();
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

  const conn       = status?.connection;
  const isConnected = conn?.status === 'ok';

  return (
    <>
      {/* Header */}
      <div className="page-header">
        <span className="page-header-title">Synchronisation Outlook</span>
        <div className="page-header-right">
          {!loading && (
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              background: isConnected ? '#dcfce7' : 'var(--red-mid)',
              color: isConnected ? '#166534' : 'var(--red-dark)',
              borderRadius: 99, padding: '3px 12px', fontSize: '0.78rem', fontWeight: 600,
            }}>
              <span style={{
                width: 7, height: 7, borderRadius: '50%',
                background: isConnected ? '#16a34a' : 'var(--red)',
                display: 'inline-block',
              }} />
              {isConnected ? 'Connecté' : 'Non connecté'}
            </span>
          )}
          <button
            className="btn btn-primary"
            onClick={handleSync}
            disabled={syncing}
          >
            {syncing
              ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Synchro…</>
              : '⟳ Lancer la synchro'}
          </button>
        </div>
      </div>

      <div className="page-content">

        {/* Info boite mail */}
        {conn?.mailbox && (
          <div className="alert alert-info" style={{ marginBottom: 20 }}>
            <span>✉</span>
            <span>Boite surveillée : <strong>{conn.mailbox}</strong></span>
          </div>
        )}

        {/* Erreur de connexion */}
        {!loading && conn?.status === 'error' && (
          <div className="alert alert-error" style={{ marginBottom: 20 }}>
            <span>⚠</span>
            <div>
              <strong>Connexion impossible :</strong> {conn.error}
              <br />
              <span style={{ fontSize: '0.8rem', marginTop: 4, display: 'block' }}>
                Vérifiez <code>AZURE_TENANT_ID</code>, <code>AZURE_CLIENT_ID</code>,
                <code>AZURE_CLIENT_SECRET</code> et <code>OUTLOOK_MAILBOX</code> dans le fichier <code>.env</code>.
              </span>
            </div>
          </div>
        )}

        {/* Rapport de synchro */}
        {report && (
          <div className={`alert ${report.success ? 'alert-success' : 'alert-error'}`} style={{ marginBottom: 20, flexDirection: 'column', alignItems: 'stretch' }}>
            <div style={{ fontWeight: 700, marginBottom: 12 }}>
              {report.success ? '✓ Synchronisation terminée' : '⚠ Synchronisation avec erreurs'}
            </div>
            <div className="kpi-grid" style={{ margin: 0 }}>
              {[
                { label: 'Emails analysés', value: report.emailsScanned ?? 0, color: '#1a1a1a' },
                { label: 'CVs trouvés',     value: report.cvsFound ?? 0,      color: '#1d4ed8' },
                { label: 'CVs créés',       value: report.cvsCreated ?? 0,    color: '#16a34a' },
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
            <div className="kpi-card" style={{ '--kpi-color': 'var(--red)' }}>
              <div className="kpi-value">{status.totalEmailsProcessed ?? 0}</div>
              <div className="kpi-label">Emails traités</div>
            </div>
            <div className="kpi-card" style={{ '--kpi-color': '#1a1a1a' }}>
              <div className="kpi-value">{status.totalSyncs ?? 0}</div>
              <div className="kpi-label">Synchronisations</div>
            </div>
            <div className="kpi-card" style={{ '--kpi-color': '#16a34a' }}>
              <div className="kpi-value">
                {status.syncHistory?.reduce((s, h) => s + (h.cvsCreated || 0), 0) ?? 0}
              </div>
              <div className="kpi-label">CVs importés</div>
            </div>
            <div className="kpi-card" style={{ '--kpi-color': '#dc2626' }}>
              <div className="kpi-value">
                {status.syncHistory?.reduce((s, h) => s + (h.cvsError || 0), 0) ?? 0}
              </div>
              <div className="kpi-label">Erreurs totales</div>
            </div>
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
                    <th>Créés</th>
                    <th>Erreurs</th>
                    <th>Déclencheur</th>
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
                      <td style={{ color: s.cvsError > 0 ? 'var(--red)' : 'var(--gray-400)' }}>
                        {s.cvsError}
                      </td>
                      <td>
                        <span className="badge badge-gray">{s.triggeredBy}</span>
                      </td>
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
              <span className="card-title">Journal des emails ({status?.totalEmailsProcessed ?? 0})</span>
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
                            <div style={{ fontSize: '0.72rem', color: 'var(--red)' }}>
                              → {log.candidatName}
                            </div>
                          )}
                        </td>
                        <td style={{ fontSize: '0.78rem', color: 'var(--text-muted)', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
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
            Chargement du statut…
          </div>
        )}
      </div>
    </>
  );
}
