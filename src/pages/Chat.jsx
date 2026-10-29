import { useEffect, useMemo, useRef, useState } from 'react';
import { BookOpen, LoaderCircle, MessageSquarePlus, Search } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { useTranslation } from 'react-i18next';
import {
    createSupportChatSession,
    getSupportChatMessages,
    listSupportChatSessions,
    prepareLearning,
} from '../services/chatbot.service.js';
import stylesChat from '../assets/css/Chat.module.css';

const MAX_REQUEST_LENGTH = 1500;
const API_URL = import.meta.env.VITE_API_URL || '';

// sessionId/onSessionChange cho phép Support Workspace chọn hội thoại từ bên ngoài.
function Chat({ sessionId: externalSessionId = '', onSessionChange } = {}) {
    const { t } = useTranslation();
    const [sessions, setSessions] = useState([]);
    const [selectedSessionId, setSelectedSessionId] = useState(externalSessionId);
    const [search, setSearch] = useState('');
    const [messages, setMessages] = useState([]);
    const [contentIntro, setContentIntro] = useState('');
    const [text, setText] = useState('');
    const [isLoadingSessions, setIsLoadingSessions] = useState(true);
    const [isLoadingMessages, setIsLoadingMessages] = useState(false);
    const [isLearning, setIsLearning] = useState(false);
    const [error, setError] = useState('');
    const [learningStatus, setLearningStatus] = useState('');
    const lastMessageRef = useRef(null);

    useEffect(() => {
        const controller = new AbortController();
        const loadSessions = async () => {
            try {
                const loaded = await listSupportChatSessions({ signal: controller.signal });
                if (controller.signal.aborted) return;
                setSessions(Array.isArray(loaded) ? loaded : []);
                if (loaded?.length) setSelectedSessionId((current) => current || loaded[0].session_id);
            } catch (requestError) {
                if (!controller.signal.aborted) setError(requestError?.response?.data?.detail?.message || t('chat.historyError', { defaultValue: 'Không thể tải lịch sử hội thoại.' }));
            } finally {
                if (!controller.signal.aborted) setIsLoadingSessions(false);
            }
        };
        loadSessions();
        return () => controller.abort();
    }, [t]);

    useEffect(() => {
        if (externalSessionId) setSelectedSessionId(externalSessionId);
    }, [externalSessionId]);

    useEffect(() => {
        if (!selectedSessionId) {
            setMessages([]);
            return undefined;
        }
        const controller = new AbortController();
        setIsLoadingMessages(true);
        setError('');
        getSupportChatMessages(selectedSessionId, { signal: controller.signal })
            .then((result) => {
                if (!controller.signal.aborted) setMessages(result.messages || []);
            })
            .catch((requestError) => {
                if (controller.signal.aborted) return;
                setMessages([]);
                // Hội thoại chatbot (chat_history) không có trong bảng support-chat.
                if (requestError?.response?.status === 404) {
                    setError(t('chat.notInSupport', { defaultValue: 'Hội thoại này chưa có trong hệ thống hỗ trợ ticket.' }));
                    return;
                }
                setError(requestError?.response?.data?.detail?.message || t('chat.historyError', { defaultValue: 'Không thể tải lịch sử hội thoại.' }));
            })
            .finally(() => {
                if (!controller.signal.aborted) setIsLoadingMessages(false);
            });
        return () => controller.abort();
    }, [selectedSessionId, t]);

    useEffect(() => {
        lastMessageRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, [messages]);

    useEffect(() => {
        const eventSource = new EventSource(`${API_URL}/intro-stream`);
        setContentIntro('');
        eventSource.onmessage = (event) => {
            if (event.data === '[DONE]') eventSource.close();
            else setContentIntro((current) => `${current} ${event.data}`);
        };
        eventSource.onerror = () => eventSource.close();
        return () => eventSource.close();
    }, []);

    const filteredSessions = useMemo(() => {
        const keyword = search.trim().toLowerCase();
        if (!keyword) return sessions;
        return sessions.filter((session) => session.product_models?.join(' ').toLowerCase().includes(keyword));
    }, [search, sessions]);
    const selectedSession = sessions.find((session) => session.session_id === selectedSessionId);
    const sessionTitle = (session) => session?.product_models?.join(', ') || t('chat.untitled', { defaultValue: 'Hội thoại hỗ trợ' });

    const selectSession = (sessionId) => {
        setSelectedSessionId(sessionId);
        onSessionChange?.(sessionId);
    };

    const createSession = async () => {
        setError('');
        try {
            const session = await createSupportChatSession();
            setSessions((current) => [session, ...current]);
            selectSession(session.session_id);
        } catch (requestError) {
            setError(requestError?.response?.data?.detail?.message || t('chat.sessionError', { defaultValue: 'Không thể tạo hội thoại mới.' }));
        }
    };

    const runLearning = async () => {
        if (!selectedSessionId || isLearning) return;
        setIsLearning(true);
        setLearningStatus('');
        setError('');
        try {
            const result = await prepareLearning(selectedSessionId);
            setLearningStatus(result.status === 'ready'
                ? t('chat.learningReady', { defaultValue: 'Đã kiểm tra và che dữ liệu nhạy cảm thành công.' })
                : t('chat.learningSkipped', { defaultValue: `Hội thoại chưa được nạp: ${result.reason || 'không đủ dữ liệu'}.` }));
        } catch (requestError) {
            setError(requestError?.response?.data?.detail?.message || t('chat.learningError', { defaultValue: 'Không thể nạp hội thoại vào kho tri thức.' }));
        } finally {
            setIsLearning(false);
        }
    };

    return (
        <div className={stylesChat.chatLayout}>
            <aside className={stylesChat.chatSidebar} aria-label={t('chat.history', { defaultValue: 'Hội thoại' })}>
                <div className={stylesChat.sidebarHeader}>
                    <h2>{t('chat.recent', { defaultValue: 'Hội thoại gần đây' })}</h2>
                    <button type="button" className={stylesChat.newChatButton} onClick={createSession} aria-label={t('chat.new', { defaultValue: 'Tạo hội thoại mới' })}>
                        <MessageSquarePlus size={18} aria-hidden="true" />
                    </button>
                </div>
                <label className={stylesChat.sessionSearch}>
                    <Search size={16} aria-hidden="true" />
                    <input
                        value={search}
                        onChange={(event) => setSearch(event.target.value)}
                        placeholder={t('chat.searchPlaceholder', { defaultValue: 'Tìm theo model' })}
                        aria-label={t('chat.search', { defaultValue: 'Tìm hội thoại' })}
                    />
                </label>
                {isLoadingSessions ? (
                    <LoaderCircle className={stylesChat.loadingIcon} size={20} aria-label={t('chat.loading', { defaultValue: 'Đang tải' })} />
                ) : (
                    <div className={stylesChat.sessionList}>
                        {filteredSessions.map((session) => (
                            <button
                                type="button"
                                key={session.session_id}
                                className={`${stylesChat.sessionItem} ${selectedSessionId === session.session_id ? stylesChat.selectedSession : ''}`}
                                onClick={() => selectSession(session.session_id)}
                            >
                                <strong>{sessionTitle(session)}</strong>
                                <small>{new Date(session.created_at).toLocaleString('vi-VN')}</small>
                            </button>
                        ))}
                    </div>
                )}
                <span className={stylesChat.sessionCount}>
                    {t('chat.count', { count: filteredSessions.length, defaultValue: '{{count}} hội thoại' })}
                </span>
            </aside>

            <main className={stylesChat.chatMain}>
                {selectedSession && (
                    <header className={stylesChat.chatHeader}>
                        <strong>{sessionTitle(selectedSession)}</strong>
                        <small>{new Date(selectedSession.created_at).toLocaleString('vi-VN')}</small>
                    </header>
                )}
                <div className={stylesChat.frameChat}>
                    {isLoadingMessages && <LoaderCircle className={stylesChat.loadingIcon} size={24} aria-label={t('chat.loading', { defaultValue: 'Đang tải' })} />}
                    {!isLoadingMessages && messages.length === 0 && (
                        <div className={stylesChat.emptyChat}>
                            <h1>{t('chatbot.titleContent')}</h1>
                            <ReactMarkdown>{contentIntro}</ReactMarkdown>
                        </div>
                    )}
                    {messages.map((message, index) => (
                        <div
                            className={message.sender_role === 'user' ? stylesChat.userBubble : stylesChat.staffBubble}
                            ref={index === messages.length - 1 ? lastMessageRef : null}
                            key={message.id}
                            style={{ fontSize: '16px' }}
                        >
                            {message.sender_role === 'staff' ? <ReactMarkdown>{message.message_text}</ReactMarkdown> : message.message_text}
                        </div>
                    ))}
                </div>

                {(error || learningStatus) && <p className={error ? stylesChat.errorMessage : stylesChat.statusMessage} role={error ? 'alert' : 'status'}>{error || learningStatus}</p>}
                <div className={stylesChat.chatComposer}>
                    <textarea
                        value={text}
                        placeholder={t('chatbot.placeholder')}
                        maxLength={MAX_REQUEST_LENGTH}
                        onChange={(event) => setText(event.target.value)}
                        aria-label={t('chatbot.messageLabel', { defaultValue: 'Tin nhắn' })}
                    />
                    <button type="button" onClick={runLearning} disabled={!selectedSessionId || isLearning} aria-label={t('chat.learning', { defaultValue: 'Nạp vào kho tri thức' })}>
                        {isLearning ? <LoaderCircle className={stylesChat.loadingIcon} size={18} /> : <BookOpen size={18} />}
                    </button>
                </div>
            </main>
        </div>
    );
}

export default Chat;
