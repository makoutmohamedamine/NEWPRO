import { Link, useLocation } from 'react-router-dom';

const NAV_LINKS = [
    { to: '/',        label: 'Dashboard' },
    { to: '/candidats', label: 'Candidats' },
    { to: '/postes',  label: 'Postes' },
    { to: '/outlook', label: '⟳ Outlook' },
];

export default function Navbar({ onLogout }) {
    const location = useLocation();

    return (
        <nav style={{
            background: '#1e293b', padding: '0.75rem 2rem',
            display: 'flex', gap: '0.5rem', alignItems: 'center',
        }}>
            <span style={{ color: '#38bdf8', fontWeight: 700, fontSize: '1.1rem', marginRight: '1rem' }}>
                CV Manager
            </span>

            {NAV_LINKS.map(({ to, label }) => {
                const active = location.pathname === to;
                return (
                    <Link
                        key={to}
                        to={to}
                        style={{
                            color: active ? '#38bdf8' : '#cbd5e1',
                            textDecoration: 'none',
                            padding: '0.4rem 0.9rem',
                            borderRadius: '6px',
                            background: active ? 'rgba(56,189,248,0.12)' : 'transparent',
                            fontWeight: active ? 600 : 400,
                            fontSize: '0.9rem',
                            transition: 'background 0.15s',
                        }}
                    >
                        {label}
                    </Link>
                );
            })}

            <button
                onClick={onLogout}
                style={{
                    marginLeft: 'auto', background: '#ef4444', color: '#fff',
                    border: 'none', padding: '0.45rem 1rem', borderRadius: '6px',
                    cursor: 'pointer', fontSize: '0.875rem',
                }}
            >
                Déconnexion
            </button>
        </nav>
    );
}
