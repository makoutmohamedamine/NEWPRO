import { Link, useLocation } from 'react-router-dom';

const Icons = {
  dashboard: <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></svg>,
  dossiers: <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" /></svg>,
  candidats: <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" /></svg>,
  postes: <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>,
  entretiens: <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>,
  chat: <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h8M8 14h5M5 20l1.5-3A8 8 0 1119 5a8 8 0 01-12.5 12z" /></svg>,
  outlook: <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>,
    ia: <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>,
  users: <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" /></svg>,
  logout: <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>,
};

export default function Sidebar({ onLogout, currentUser, newCount = 0 }) {
  const { pathname } = useLocation();
  const isAdmin = currentUser?.role === 'admin' || currentUser?.is_staff === true || currentUser?.is_superuser === true;

  const NAV = [
    {
      section: 'Principal',
      links: [
        { to: '/',          icon: Icons.dashboard, label: 'TalentMatch IA' },
        { to: '/dossiers-cv',  icon: Icons.dossiers,  label: 'Dossiers CV' },
        { to: '/candidats', icon: Icons.candidats, label: 'Candidats' },
      ],
    },
    {
      section: 'Recrutement',
      links: [
        { to: '/postes',      icon: Icons.postes,   label: 'Fiches de poste' },
        { to: '/entretiens',  icon: Icons.entretiens, label: 'Entretiens' },
        { to: '/chat-rh',     icon: Icons.chat,     label: 'Chat RH' },
        { to: '/analyse-ia',  icon: Icons.ia,       label: 'Analyse IA' },
      ],
    },
    ...(isAdmin ? [{
      section: 'Administration',
      links: [
        { to: '/utilisateurs', icon: Icons.users, label: 'Utilisateurs' },
      ],
    }] : []),
  ];

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <img
          src="/logocld.png"
          alt="TalentMatch IA"
          style={{ height: 36, width: 'auto', objectFit: 'contain', display: 'block' }}
        />
      </div>

      {/* Info utilisateur connecté */}
      {currentUser && (
        <div style={{
          padding: '10px 16px 14px',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          marginBottom: 8,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: '50%',
              background: isAdmin ? 'rgba(124,58,237,0.2)' : 'rgba(8,145,178,0.2)',
              color: isAdmin ? '#a78bfa' : '#22d3ee',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontWeight: 800, fontSize: '0.8rem', flexShrink: 0,
            }}>
              {(currentUser.first_name?.[0] || currentUser.username[0]).toUpperCase()}
            </div>
            <div>
              <div style={{ color: '#f1f5f9', fontSize: '0.82rem', fontWeight: 700 }}>
                {currentUser.first_name || currentUser.username}
              </div>
              <div style={{
                fontSize: '0.7rem', fontWeight: 600,
                color: isAdmin ? '#a78bfa' : '#22d3ee',
              }}>
                {isAdmin ? 'Administrateur' : 'Recruteur RH'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Navigation */}
      <nav className="sidebar-nav">
        {NAV.map((section) => (
          <div key={section.section}>
            <div className="sidebar-section-label">{section.section}</div>
            {section.links.map(({ to, icon, label }) => {
              const active = pathname === to;
              const showBadge = to === '/dossiers-cv' && newCount > 0;
              return (
                <Link
                  key={to}
                  to={to}
                  className={`sidebar-link${active ? ' active' : ''}`}
                >
                  <span className="icon">{icon}</span>
                  {label}
                  {showBadge && (
                    <span className="sidebar-badge">{newCount}</span>
                  )}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Footer — déconnexion */}
      <div className="sidebar-footer">
        <button
          onClick={onLogout}
          className="sidebar-link"
          style={{ width: '100%', background: 'none', border: 'none', color: '#a1a1aa' }}
        >
          <span className="icon">{Icons.logout}</span>
          Déconnexion
        </button>
      </div>
    </aside>
  );
}
