import { useCallback, useEffect, useRef, useState } from 'react';
import {
  askChatRH,
  clearChatHistory,
  createChatConversation,
  deleteChatConversation,
  getChatConversations,
  getChatHistory,
} from '../api/api';

const WELCOME_MESSAGE = {
  role: 'assistant',
  text: "Bonjour, je suis TalentMatch IA. Posez vos questions RH sur candidats, postes, statuts et domaines. Utilisez « Nouveau chat » pour une conversation vierge, ou rouvrez une conversation dans l'archive à gauche.",
  highlights: [],
  suggestedActions: [],
};

function mapServerMessage(m) {
  return {
    id: m.id,
    role: m.role,
    text: m.text,
    highlights: m.highlights || [],
    suggestedActions: m.suggestedActions || [],
    createdAt: m.createdAt,
  };
}

export default function ChatRH() {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingBootstrap, setLoadingBootstrap] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([WELCOME_MESSAGE]);
  const bottomRef = useRef(null);

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    });
  }, []);

  const refreshConversationList = useCallback(async () => {
    try {
      const res = await getChatConversations();
      setConversations(res.data?.conversations || []);
    } catch {
      setConversations([]);
    }
  }, []);

  const loadMessagesFor = useCallback(
    async (conversationId) => {
      if (conversationId == null) return;
      setLoadingMessages(true);
      try {
        const res = await getChatHistory({ conversation: conversationId, limit: 300 });
        const list = res.data?.messages || [];
        setMessages(list.length > 0 ? list.map(mapServerMessage) : [WELCOME_MESSAGE]);
      } catch {
        setMessages([WELCOME_MESSAGE]);
      } finally {
        setLoadingMessages(false);
        setTimeout(scrollToBottom, 80);
      }
    },
    [scrollToBottom],
  );

  const bootstrap = useCallback(async () => {
    setLoadingBootstrap(true);
    try {
      let list = [];
      try {
        const res = await getChatConversations();
        list = res.data?.conversations || [];
      } catch {
        list = [];
      }
      if (list.length === 0) {
        const cr = await createChatConversation({});
        const c = cr.data?.conversation;
        if (c) list = [c];
      }
      setConversations(list);
      const firstId = list[0]?.id ?? null;
      setActiveConversationId(firstId);
      if (firstId != null) {
        await loadMessagesFor(firstId);
      } else {
        setMessages([WELCOME_MESSAGE]);
      }
    } catch {
      setMessages([WELCOME_MESSAGE]);
    } finally {
      setLoadingBootstrap(false);
    }
  }, [loadMessagesFor]);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, scrollToBottom]);

  const handleNewChat = async () => {
    try {
      const cr = await createChatConversation({});
      const c = cr.data?.conversation;
      if (!c) return;
      setConversations((prev) => [c, ...prev]);
      setActiveConversationId(c.id);
      setMessages([WELCOME_MESSAGE]);
    } catch {
      window.alert('Impossible de créer une nouvelle conversation.');
    }
  };

  const selectConversation = (id) => {
    if (id === activeConversationId) return;
    setActiveConversationId(id);
    loadMessagesFor(id);
  };

  const handleDeleteConversation = async (e, convId) => {
    e.stopPropagation();
    if (!window.confirm('Supprimer cette conversation et tout son contenu ?')) return;
    try {
      await deleteChatConversation(convId);
      const res = await getChatConversations();
      const next = res.data?.conversations || [];
      setConversations(next);
      if (convId === activeConversationId) {
        if (next.length > 0) {
          setActiveConversationId(next[0].id);
          await loadMessagesFor(next[0].id);
        } else {
          const cr = await createChatConversation({});
          const c = cr.data?.conversation;
          if (c) {
            setConversations([c]);
            setActiveConversationId(c.id);
            setMessages([WELCOME_MESSAGE]);
          } else {
            setConversations([]);
            setActiveConversationId(null);
            setMessages([WELCOME_MESSAGE]);
          }
        }
      }
    } catch {
      window.alert('Suppression impossible pour le moment.');
    }
  };

  const handleClearAll = async () => {
    if (!window.confirm("Supprimer toutes les conversations et l'archive du Chat RH pour votre compte ?")) return;
    try {
      await clearChatHistory();
      await bootstrap();
    } catch {
      window.alert("Impossible de tout effacer pour le moment.");
    }
  };

  const send = async () => {
    const q = question.trim();
    if (!q || loading || activeConversationId == null) return;
    setMessages((prev) => [...prev, { role: 'user', text: q }]);
    setQuestion('');
    setLoading(true);
    try {
      const res = await askChatRH(q, activeConversationId);
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: res.data?.answer || 'Je n ai pas de reponse pour le moment.',
          highlights: res.data?.highlights || [],
          suggestedActions: res.data?.suggestedActions || [],
        },
      ]);
      await refreshConversationList();
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: err?.response?.data?.error || 'Erreur chatbot, reessayez.',
          highlights: [],
          suggestedActions: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <span className="page-header-title">Chat RH - TalentMatch IA</span>
        <div className="page-header-right" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button type="button" className="btn btn-ghost btn-sm" onClick={handleClearAll} disabled={loadingBootstrap}>
            Tout effacer
          </button>
        </div>
      </div>

      <div className="page-content chat-rh-page chat-rh-shell">
        <aside className="card chat-rh-sidebar">
          <button type="button" className="btn btn-primary chat-rh-new-btn" onClick={handleNewChat}>
            + Nouveau chat
          </button>
          <div className="chat-rh-sidebar-title">Conversations</div>
          {loadingBootstrap ? (
            <div className="chat-rh-sidebar-loading">Chargement…</div>
          ) : (
            <ul className="chat-rh-conv-list">
              {conversations.map((c) => (
                <li key={c.id}>
                  <div
                    role="button"
                    tabIndex={0}
                    className={`chat-rh-conv-item${c.id === activeConversationId ? ' chat-rh-conv-item--active' : ''}`}
                    onClick={() => selectConversation(c.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        selectConversation(c.id);
                      }
                    }}
                  >
                    <div className="chat-rh-conv-item-top">
                      <span className="chat-rh-conv-title">{c.title || 'Conversation'}</span>
                      <button
                        type="button"
                        className="chat-rh-conv-delete"
                        title="Supprimer cette conversation"
                        aria-label="Supprimer"
                        onClick={(e) => handleDeleteConversation(e, c.id)}
                      >
                        ×
                      </button>
                    </div>
                    {c.preview ? <div className="chat-rh-conv-preview">{c.preview}</div> : null}
                    <div className="chat-rh-conv-meta">
                      {c.messageCount != null ? `${c.messageCount} message(s)` : ''}
                      {c.updatedAt
                        ? ` · ${new Date(c.updatedAt).toLocaleString('fr-FR', {
                            day: '2-digit',
                            month: 'short',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}`
                        : ''}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <div className="chat-rh-main">
          <div className="card chat-rh-messages-card">
            {loadingMessages ? (
              <div className="chat-rh-loading">{"Chargement de la conversation…"}</div>
            ) : (
              <div className="chat-rh-messages-scroll">
                {messages.map((m, i) => (
                  <div
                    key={m.id != null ? `msg-${m.id}` : `${m.role}-${i}-${m.createdAt || ''}`}
                    className={`chat-rh-bubble chat-rh-bubble--${m.role}`}
                  >
                    {m.createdAt && m.id != null && (
                      <div className="chat-rh-bubble-meta">
                        {new Date(m.createdAt).toLocaleString('fr-FR', {
                          day: '2-digit',
                          month: 'short',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </div>
                    )}
                    <div className="chat-rh-bubble-text">{m.text}</div>
                    {m.highlights?.length > 0 && (
                      <div className="chat-rh-bubble-highlights">
                        {m.highlights.map((h, hi) => (
                          <span key={hi}>• {h}</span>
                        ))}
                      </div>
                    )}
                    {m.suggestedActions?.length > 0 && (
                      <div className="chat-rh-bubble-actions">
                        {m.suggestedActions.map((a, ai) => (
                          <span key={ai}>→ {a}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {loading && (
                  <div className="chat-rh-bubble chat-rh-bubble--assistant chat-rh-bubble--typing">
                    <span className="chat-rh-typing">Analyse en cours…</span>
                  </div>
                )}
                <div ref={bottomRef} />
              </div>
            )}
          </div>

          <div className="card card-body chat-rh-input-row">
            <input
              className="form-input"
              placeholder="Ex: Qui sont les meilleurs candidats pour Comptable Junior ?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && send()}
              disabled={activeConversationId == null || loadingBootstrap}
            />
            <button
              className="btn btn-primary"
              type="button"
              onClick={send}
              disabled={loading || !question.trim() || activeConversationId == null || loadingBootstrap}
            >
              {loading ? 'Analyse...' : 'Envoyer'}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
