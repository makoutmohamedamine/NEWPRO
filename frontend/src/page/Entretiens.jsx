import { useCallback, useEffect, useMemo, useState } from 'react';
import { Calendar, dateFnsLocalizer } from 'react-big-calendar';
import { format, getDay, parse, startOfWeek } from 'date-fns';
import { fr } from 'date-fns/locale';
import {
  createEntretien,
  deleteEntretien,
  getCandidatures,
  getEntretiens,
  updateEntretien,
} from '../api/api';
import 'react-big-calendar/lib/css/react-big-calendar.css';

const locales = { fr };

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: (date, options) => startOfWeek(date, { ...options, weekStartsOn: 1 }),
  getDay,
  locales,
});

const CAL_MESSAGES = {
  allDay: 'Journée',
  previous: 'Précédent',
  next: 'Suivant',
  today: "Aujourd'hui",
  month: 'Mois',
  week: 'Semaine',
  day: 'Jour',
  agenda: 'Liste',
  date: 'Date',
  time: 'Heure',
  event: 'Entretien',
  noEventsInRange: 'Aucun entretien sur cette période.',
  showMore: (total) => `+ ${total} autres`,
};

const TYPE_OPTIONS = [
  { value: 'rh', label: 'Entretien RH' },
  { value: 'technique', label: 'Entretien technique' },
  { value: 'final', label: 'Entretien final' },
  { value: 'autre', label: 'Autre' },
];

const TYPE_COLORS = {
  rh: { bg: '#dbeafe', border: '#1d4ed8', text: '#1e3a8a' },
  technique: { bg: '#e0e7ff', border: '#4f46e5', text: '#312e81' },
  final: { bg: '#dcfce7', border: '#15803d', text: '#14532d' },
  autre: { bg: '#f4f4f5', border: '#71717a', text: '#3f3f46' },
};

function pad2(n) {
  return String(n).padStart(2, '0');
}

function toDatetimeLocalValue(d) {
  if (!(d instanceof Date) || Number.isNaN(d.getTime())) return '';
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

function fromDatetimeLocalValue(s) {
  if (!s) return null;
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

function toClickableLink(value) {
  const raw = String(value || '').trim();
  if (!raw) return null;
  if (/^https?:\/\//i.test(raw)) return raw;
  if (/^www\./i.test(raw)) return `https://${raw}`;
  return null;
}

function emptyForm() {
  return {
    candidature: '',
    titre: '',
    type_entretien: 'rh',
    debut: '',
    fin: '',
    lieu: '',
    notes: '',
  };
}

export default function Entretiens() {
  const [entretiens, setEntretiens] = useState([]);
  const [candidatures, setCandidatures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [view, setView] = useState('week');
  const [date, setDate] = useState(new Date());
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setError('');
    setLoading(true);
    try {
      const [entRes, candRes] = await Promise.all([getEntretiens(), getCandidatures()]);
      const ent = Array.isArray(entRes.data) ? entRes.data : entRes.data?.results || [];
      const cand = Array.isArray(candRes.data) ? candRes.data : candRes.data?.results || [];
      setEntretiens(ent);
      setCandidatures(cand);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Impossible de charger les données.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const events = useMemo(
    () =>
      entretiens.map((e) => ({
        id: e.id,
        title:
          e.titre?.trim() ||
          `${e.candidat_prenom || ''} ${e.candidat_nom || ''} — ${e.type_entretien_label || ''}`.trim(),
        start: new Date(e.debut),
        end: new Date(e.fin),
        resource: e,
      })),
    [entretiens],
  );

  const eventPropGetter = useCallback((event) => {
    const t = event.resource?.type_entretien || 'autre';
    const c = TYPE_COLORS[t] || TYPE_COLORS.autre;
    return {
      style: {
        backgroundColor: c.bg,
        borderLeft: `4px solid ${c.border}`,
        color: c.text,
        borderRadius: 6,
      },
    };
  }, []);

  const upcomingEntretiens = useMemo(() => {
    const now = new Date();
    return entretiens
      .filter((e) => {
        const start = new Date(e.debut);
        return !Number.isNaN(start.getTime()) && start >= now;
      })
      .sort((a, b) => new Date(a.debut) - new Date(b.debut))
      .slice(0, 8);
  }, [entretiens]);

  const openCreate = (rangeStart, rangeEnd) => {
    setError('');
    setEditingId(null);
    const start = rangeStart instanceof Date ? rangeStart : new Date();
    const end = rangeEnd instanceof Date ? rangeEnd : new Date(start.getTime() + 60 * 60 * 1000);
    setForm({
      ...emptyForm(),
      debut: toDatetimeLocalValue(start),
      fin: toDatetimeLocalValue(end),
    });
    setModalOpen(true);
  };

  const openEdit = (row) => {
    setError('');
    setEditingId(row.id);
    setForm({
      candidature: String(row.candidature),
      titre: row.titre || '',
      type_entretien: row.type_entretien || 'rh',
      debut: toDatetimeLocalValue(new Date(row.debut)),
      fin: toDatetimeLocalValue(new Date(row.fin)),
      lieu: row.lieu || '',
      notes: row.notes || '',
    });
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingId(null);
    setForm(emptyForm());
  };

  const handleSubmit = async (ev) => {
    ev.preventDefault();
    const debutIso = fromDatetimeLocalValue(form.debut);
    const finIso = fromDatetimeLocalValue(form.fin);
    if (!form.candidature || !debutIso || !finIso) {
      setError('Candidature, début et fin sont obligatoires.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const payload = {
        candidature: Number(form.candidature),
        titre: form.titre,
        type_entretien: form.type_entretien,
        debut: debutIso,
        fin: finIso,
        lieu: form.lieu,
        notes: form.notes,
      };
      if (editingId) {
        await updateEntretien(editingId, payload);
      } else {
        await createEntretien(payload);
      }
      await load();
      closeModal();
    } catch (e) {
      const msg = e.response?.data;
      if (typeof msg === 'object' && msg !== null) {
        const parts = Object.entries(msg).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`);
        setError(parts.join(' — ') || 'Erreur de sauvegarde.');
      } else {
        setError(e.message || 'Erreur de sauvegarde.');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!editingId || !window.confirm('Supprimer cet entretien ?')) return;
    setSaving(true);
    setError('');
    try {
      await deleteEntretien(editingId);
      await load();
      closeModal();
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Suppression impossible.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <span className="page-header-title">Entretiens</span>
        <div className="page-header-right">
          <button type="button" className="btn btn-primary" onClick={() => openCreate(new Date(), new Date(Date.now() + 3600000))}>
            Nouvel entretien
          </button>
        </div>
      </div>

      <div className="page-content entretiens-page">
        <p className="entretiens-intro">Planifiez les entretiens sur le calendrier (glisser un créneau en vue semaine ou jour), ou créez un entretien manuellement.</p>

        {error && !modalOpen && <div className="alert alert-error entretiens-banner">{error}</div>}

        <div className="entretiens-layout">
        <section className="card entretiens-calendar-card">
          {loading ? (
            <div className="entretiens-loading">Chargement du calendrier…</div>
          ) : (
            <Calendar
              culture="fr"
              localizer={localizer}
              events={events}
              startAccessor="start"
              endAccessor="end"
              style={{ height: 640 }}
              view={view}
              onView={setView}
              date={date}
              onNavigate={setDate}
              messages={CAL_MESSAGES}
              selectable
              onSelectSlot={({ start, end }) => openCreate(start, end)}
              onSelectEvent={(ev) => openEdit(ev.resource)}
              eventPropGetter={eventPropGetter}
              views={['month', 'week', 'day', 'agenda']}
            />
          )}
        </section>

        <aside className="card entretiens-side">
          <h2 className="entretiens-side-title">À venir</h2>
          <ul className="entretiens-upcoming">
            {upcomingEntretiens.map((e) => (
                <li key={e.id}>
                  <button type="button" className="entretiens-upcoming-row" onClick={() => openEdit(e)}>
                    <span className="entretiens-upcoming-date">
                      {format(new Date(e.debut), 'EEE d MMM, HH:mm', { locale: fr })}
                    </span>
                    <span className="entretiens-upcoming-label">
                      {e.titre?.trim() || `${e.candidat_prenom} ${e.candidat_nom}`}
                    </span>
                    <span className="entretiens-upcoming-meta">{e.poste_titre}</span>
                    {toClickableLink(e.lieu) ? (
                      <a
                        href={toClickableLink(e.lieu)}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(ev) => ev.stopPropagation()}
                      >
                        Ouvrir le lien de réunion
                      </a>
                    ) : null}
                  </button>
                </li>
              ))}
            {upcomingEntretiens.length === 0 && (
              <li className="entretiens-empty">Aucun entretien à venir. Créez-en un ou sélectionnez un créneau sur le calendrier.</li>
            )}
          </ul>
        </aside>
        </div>
      </div>

      {modalOpen && (
        <div className="entretiens-modal-backdrop" role="presentation" onClick={closeModal}>
          <div
            className="entretiens-modal card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="entretien-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="entretien-modal-title" className="entretiens-modal-title">
              {editingId ? "Modifier l'entretien" : 'Planifier un entretien'}
            </h2>
            {error && modalOpen && <div className="alert alert-error entretiens-modal-error">{error}</div>}
            <form onSubmit={handleSubmit} className="entretiens-form">
              <div className="form-group">
                <label className="form-label" htmlFor="ent-candidature">
                  Candidature
                </label>
                <select
                  id="ent-candidature"
                  className="form-select"
                  required
                  disabled={Boolean(editingId)}
                  value={form.candidature}
                  onChange={(e) => setForm({ ...form, candidature: e.target.value })}
                >
                  <option value="">— Choisir une candidature —</option>
                  {candidatures.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.candidat_prenom} {c.candidat_nom} — {c.poste_titre}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="ent-titre">
                  Titre (optionnel)
                </label>
                <input
                  id="ent-titre"
                  className="form-input"
                  value={form.titre}
                  onChange={(e) => setForm({ ...form, titre: e.target.value })}
                  placeholder="Ex. Entretien téléphonique — phase 1"
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="ent-type">
                  Type
                </label>
                <select
                  id="ent-type"
                  className="form-select"
                  value={form.type_entretien}
                  onChange={(e) => setForm({ ...form, type_entretien: e.target.value })}
                >
                  {TYPE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="entretiens-form-row">
                <div className="form-group">
                  <label className="form-label" htmlFor="ent-debut">
                    Début
                  </label>
                  <input
                    id="ent-debut"
                    className="form-input"
                    type="datetime-local"
                    required
                    value={form.debut}
                    onChange={(e) => setForm({ ...form, debut: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="ent-fin">
                    Fin
                  </label>
                  <input
                    id="ent-fin"
                    className="form-input"
                    type="datetime-local"
                    required
                    value={form.fin}
                    onChange={(e) => setForm({ ...form, fin: e.target.value })}
                  />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="ent-lieu">
                  Lieu / lien visio
                </label>
                <input
                  id="ent-lieu"
                  className="form-input"
                  value={form.lieu}
                  onChange={(e) => setForm({ ...form, lieu: e.target.value })}
                  placeholder="Bureau, Teams, etc."
                />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="ent-notes">
                  Notes
                </label>
                <textarea
                  id="ent-notes"
                  className="form-textarea"
                  rows={3}
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                />
              </div>
              <div className="entretiens-form-actions">
                <button type="button" className="btn btn-ghost" onClick={closeModal}>
                  Annuler
                </button>
                {editingId && (
                  <button type="button" className="btn btn-danger-outline" onClick={handleDelete} disabled={saving}>
                    Supprimer
                  </button>
                )}
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? 'Enregistrement…' : editingId ? 'Enregistrer' : 'Créer'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
