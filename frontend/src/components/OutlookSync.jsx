import { useCallback, useEffect, useState } from 'react';
import { getOutlookStatus, triggerOutlookSync } from '../api/api';

export default function OutlookSync({ onSyncSuccess }) {
  const [status, setStatus] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);

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

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const handleSync = async () => {
    setSyncing(true);
    setReport(null);
    try {
      const res = await triggerOutlookSync();
      setReport(res.data);
      await loadStatus();
      if (onSyncSuccess) {
        setTimeout(() => onSyncSuccess(), 1000);
      }
    } catch (err) {
      setReport({
        success: false,
        errors: [err?.response?.data?.error || 'Erreur inconnue'],
        cvsCreated: 0,
        emailsScanned: 0,
        cvsFound: 0,
        cvsError: 1,
      });
    } finally {
      setSyncing(false);
    }
  };

  const conn = status?.connection;
  const isConnected = conn?.status === 'ok';

  return (
    <div className="card outlook-sync-card">
      <div className="card-header outlook-sync-head">
        <div>
          <span className="card-title">Synchronisation Outlook</span>
          <div className="outlook-sync-subtitle">Connecteur Microsoft Graph pour la boite RH</div>
        </div>
        <div className="outlook-sync-actions">
          {!loading && (
            <span className={`outlook-pill ${isConnected ? 'is-success' : 'is-error'}`}>
              <span className="outlook-pill-dot" />
              {isConnected ? 'Connecte' : 'Non connecte'}
            </span>
          )}
          <button className="btn btn-primary" onClick={handleSync} disabled={syncing}>
            {syncing ? 'Synchronisation...' : 'Lancer'}
          </button>
        </div>
      </div>

      <div className="card-body">
        {conn?.mailbox && (
          <div className="alert alert-info outlook-sync-mailbox">
            <strong>Boite surveillee</strong>
            <span className="break-anywhere">{conn.mailbox}</span>
          </div>
        )}

        {!loading && conn?.status === 'error' && (
          <div className="alert alert-error outlook-sync-error-card">
            <div className="outlook-sync-error-title">Connexion impossible</div>
            <div className="outlook-sync-error-body break-anywhere">{conn.error}</div>
          </div>
        )}

        {report && (
          <div className={`alert ${report.success ? 'alert-success' : 'alert-error'} outlook-sync-report`}>
            {report.success ? (
              <>
                <div className="outlook-sync-error-title">Synchronisation reussie</div>
                <div className="outlook-sync-report-stats">
                  <span>{report.emailsScanned} emails</span>
                  <span>{report.cvsFound} CV detectes</span>
                  <span>{report.cvsCreated} candidats crees</span>
                </div>
              </>
            ) : (
              <>
                <div className="outlook-sync-error-title">Erreur de synchronisation</div>
                <div className="outlook-sync-error-body break-anywhere">{report.errors?.[0]}</div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
