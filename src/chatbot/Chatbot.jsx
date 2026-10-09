import { useEffect, useRef, useState } from 'react';
import { LoaderCircle, Send, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { useTranslation } from 'react-i18next';
import { streamChatbotResponse } from '../services/chatbot.service.js';
import styles from './Chatbot.module.css';

const MAX_REQUEST_LENGTH = 1500;

function makeMessageId() {
    return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
}

function Chatbot({ closeWinChatbot, hidden = false, onSendingChange }) {
    const { t } = useTranslation();
    const [messages, setMessages] = useState([]);
    const [text, setText] = useState('');
    const [isSending, setIsSending] = useState(false);
    const [requestError, setRequestError] = useState('');
    const messageListRef = useRef(null);
    const activeControllerRef = useRef(null);
    const endOfMessagesRef = useRef(null);

    useEffect(() => {
        const container = messageListRef.current;
        if (container) container.scrollTop = container.scrollHeight;
        endOfMessagesRef.current?.scrollIntoView({ block: 'end' });
    }, [messages]);

    useEffect(() => {
        onSendingChange?.(isSending);
    }, [isSending, onSendingChange]);

    useEffect(() => () => activeControllerRef.current?.abort(), []);

    const sendMessage = async (event) => {
        event.preventDefault();
        const message = text.trim();
        if (!message || isSending || message.length > MAX_REQUEST_LENGTH) return;

        setRequestError('');
        setText('');
        setIsSending(true);

        const assistantId = makeMessageId();
        setMessages((current) => [
            ...current,
            { id: makeMessageId(), role: 'user', content: message },
            { id: assistantId, role: 'assistant', content: '' },
        ]);

        const controller = new AbortController();
        activeControllerRef.current = controller;

        try {
            await streamChatbotResponse(message, {
                signal: controller.signal,
                onChunk: (chunk) => {
                    setMessages((current) => current.map((item) => (
                        item.id === assistantId
                            ? { ...item, content: item.content + chunk }
                            : item
                    )));
                },
            });
        } catch (error) {
            if (!controller.signal.aborted) {
                if (error?.code === 'request_blocked' && error.message) {
                    setMessages((current) => current.map((item) => (
                        item.id === assistantId
                            ? { ...item, content: error.message }
                            : item
                    )));
                } else {
                    setRequestError(t('chatbot.sendError'));
                    setMessages((current) => current.filter((item) => (
                        item.id !== assistantId || item.content
                    )));
                }
            }
        } finally {
            if (!controller.signal.aborted) setIsSending(false);
            if (activeControllerRef.current === controller) activeControllerRef.current = null;
        }
    };

    return (
        <section
            id="home-chatbot-panel"
            className={styles.chatPanel}
            role="dialog"
            aria-label={t('chatbot.titleContent')}
            aria-hidden={hidden}
            hidden={hidden}
        >
            <header className={styles.panelHeader}>
                <div className={styles.headerIdentity}>
                    <span className={styles.statusDot} aria-hidden="true" />
                    <div>
                        <h2>{t('chatbot.titleChatbot')}</h2>
                        <p>{t('chatbot.online')}</p>
                    </div>
                </div>
                <button
                    className={styles.iconButton}
                    type="button"
                    aria-label={t('chatbot.close')}
                    onClick={closeWinChatbot}
                >
                    <X size={20} aria-hidden="true" />
                </button>
            </header>

            <div className={styles.messageList} ref={messageListRef} aria-live="polite">
                {messages.length === 0 && (
                    <div className={styles.welcomeMessage}>
                        <span className={styles.QSName} aria-hidden="true">QS</span>
                        <p>{t('chatbot.description')}</p>
                    </div>
                )}

                {messages.map((message) => (
                    <article
                        className={message.role === 'user' ? styles.userMessage : styles.assistantMessage}
                        key={message.id}
                    >
                        {message.role === 'assistant' ? (
                            message.content
                                ? <ReactMarkdown>{message.content}</ReactMarkdown>
                                : isSending && <span className={styles.typingIndicator}>{t('chatbot.thinking')}</span>
                        ) : message.content}
                    </article>
                ))}
                {requestError && <p className={styles.errorMessage} role="alert">{requestError}</p>}
                <div ref={endOfMessagesRef} />
            </div>

            <form className={styles.composer} onSubmit={sendMessage}>
                <label className={styles.visuallyHidden} htmlFor="home-chatbot-input">
                    {t('chatbot.messageLabel')}
                </label>
                <input
                    id="home-chatbot-input"
                    className={styles.messageInput}
                    type="text"
                    maxLength={MAX_REQUEST_LENGTH}
                    placeholder={t('chatbot.placeholder')}
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    disabled={isSending}
                />
                <button
                    className={styles.sendButton}
                    type="submit"
                    aria-label={t('chatbot.send')}
                    disabled={!text.trim() || isSending}
                >
                    {isSending ? <LoaderCircle className={styles.spinningIcon} size={18} aria-hidden="true" /> : <Send size={18} aria-hidden="true" />}
                </button>
            </form>
            <p className={styles.footerNote}>{t('chatbot.footerNote')}</p>
        </section>
    );
}

export default Chatbot;
