import { useEffect, useState } from 'react';
import { getCandidats } from '../api/api';

function Avatar({ name }) {
  const initials = name
    ? name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase()
    : '?';
  return (
    <div style={{
      width: 34, height: 34, borderRadius: '50%',
      background: 'var(--red)', color: 'white',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontWeight: 700, fontSize: '0.78rem', flexShrink: 0,
    }}>
      {initials}
    </div>
  );
}

export default function Candidats() {
  const [candidats, setCandidats] = useState([]);
  const [loading, setLoading]     = useState(true);
  const [search, setSearch]       = useState('');

  useEffect(() => {
    getCandidats()
      .then(r => setCandidats(r.data))
      .finally(() => setLoading(false));
  }, []);

  const filtered = candidats.filter(c => {
    const q = search.toLowerCase();
    return (
      (c.nom || '').toLowerCase().includes(q) ||
      (c.prenom || '').toLowerCase().includes(q) ||
      (c.email || '').toLowerCase().includes(q)
    );
  });

  return (
    <>
      {/* Header */}
      <div className="page-header">
        <span className="page-header-title">Candidats</span>
        <div className="page-header-right">
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            {candidats.length} candidat{candidats.length !== 1 ? 's' : ''}
          </span>
          <input
            className="form-input"
            style={{ width: 220, padding: '6px 12px' }}
            placeholder="Rechercher…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="page-content">
        <div className="card">
          {loading ? (
            <div className="empty-state card-body">
              <div className="spinner" style={{ margin: '0 auto 12px' }} />
              Chargement…
            </div>
          ) : filtered.length > 0 ? (
            <table className="table">
              <thead>
                <tr>
                  <th>Candidat</th>
                  <th>Email</th>
                  <th>Téléphone</th>
                  <th>Date d'ajout</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(c => {
                  const fullName = `${c.prenom || ''} ${c.nom || ''}`.trim();
                  return (
                    <tr key={c.id}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <Avatar name={fullName} />
                          <span style={{ fontWeight: 600 }}>{fullName || '—'}</span>
                        </div>
                      </td>
                      <td style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>{c.email}</td>
                      <td style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>{c.telephone || '—'}</td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {c.created_at
                          ? new Date(c.created_at).toLocaleDateString('fr-FR')
                          : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <div className="empty-state card-body" style={{ padding: '3rem' }}>
              <div className="empty-state-icon">👤</div>
              <div className="empty-state-title">
                {search ? 'Aucun résultat' : 'Aucun candidat'}
              </div>
              <div style={{ fontSize: '0.875rem' }}>
                {search
                  ? `Aucun candidat ne correspond à "${search}"`
                  : 'Importez des CVs via Outlook ou uploadez-les manuellement.'}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
