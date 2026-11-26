import { useEffect, useRef, useState } from 'react';
import { ImagePlus, LoaderCircle, Mic, Send, Square, X } from 'lucide-react';
import Markdown from '../components/Markdown.jsx';
import SourceList, { Citation } from './SourceList.jsx';
import ActivityTimeline from './activity/ActivityTimeline.jsx';
import { applyStatus, guessLanguage } from './activity/activityModel.js';
import { useSpeechInput } from './useSpeechInput.js';
import { useTranslation } from 'react-i18next';
import { getWidgetHistory, streamChatbotResponse, streamCrmChatbotResponse } from '../services/chatbot.service.js';
import styles from './Chatbot.module.css';

const MAX_REQUEST_LENGTH = 1500;
// Kiểm thử kênh CRM: VITE_CHATBOT_CHANNEL=crm gửi qua /api/chat/crm với user_id mẫu.
const IS_CRM_TEST = import.meta.env.VITE_CHATBOT_CHANNEL === 'crm';
const CRM_TEST_USER_ID = import.meta.env.VITE_CRM_TEST_USER_ID || 'employee_test_001';
// Token CRM kiểm thử: VITE_* bị đóng gói vào bundle trình duyệt, chỉ dùng ở môi trường kiểm thử.
const CRM_TEST_TOKEN = import.meta.env.VITE_CRM_TEST_TOKEN || undefined;
// Gửi ảnh (WU-17 đợt 3A): CHỈ có giao diện, backend chưa nhận ảnh → sau cờ, mặc định tắt (TR-16).
// Ảnh chỉ hiện trong khung chat của trình duyệt, KHÔNG được gửi lên máy chủ.
const IMAGE_INPUT_ENABLED = import.meta.env.VITE_CHAT_IMAGE_INPUT === 'true';
const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const IMAGE_MAX_BYTES = 5 * 1024 * 1024;
const IMAGE_MAX_COUNT = 3;

function makeMessageId() {
    return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
}

function Chatbot({ closeWinChatbot, hidden = false, onSendingChange }) {
    const { t, i18n } = useTranslation();
    const [messages, setMessages] = useState([]);
    const [text, setText] = useState('');
    const [isSending, setIsSending] = useState(false);
    const [requestError, setRequestError] = useState('');
    const [attachments, setAttachments] = useState([]);
    const [attachError, setAttachError] = useState('');
    const messageListRef = useRef(null);
    const activeControllerRef = useRef(null);
    const endOfMessagesRef = useRef(null);
    const fileInputRef = useRef(null);
    const objectUrlsRef = useRef([]);
    const speech = useSpeechInput({
        lang: String(i18n?.language || '').startsWith('en') ? 'en-US' : 'vi-VN',
        onText: (value) => setText(value.slice(0, MAX_REQUEST_LENGTH)),
    });

    useEffect(() => {
        // widget-backend trả hội thoại hiện tại theo cookie; chưa có thì messages rỗng.
        // Lịch sử này là của kênh website nên bỏ qua khi kiểm thử CRM.
        if (IS_CRM_TEST) return undefined;
        const controller = new AbortController();
        getWidgetHistory({ signal: controller.signal })
            .then((history) => {
                if (controller.signal.aborted) return;
                const restoredMessages = history.messages.flatMap((item) => {
                    const entries = [{ id: `${item.id}-query`, role: 'user', content: item.query_origin }];
                    if (item.answer) {
                        // cited_sources (WU-17 đợt 2): tiêu đề, trang và ảnh ký mới của nguồn đã trích dẫn.
                        entries.push({
                            id: `${item.id}-answer`,
                            role: 'assistant',
                            content: item.answer,
                            sources: Array.isArray(item.cited_sources) ? item.cited_sources : undefined,
                        });
                    }
                    return entries;
                });
                // Khách có thể đã gửi tin trước khi lịch sử tải xong: ghép lịch sử vào trước, không ghi đè.
                setMessages((current) => [...restoredMessages, ...current]);
            })
            .catch(() => {
                if (controller.signal.aborted) return;
                setRequestError(t('chatbot.historyError', { defaultValue: 'Không thể tải lịch sử hội thoại.' }));
            });

        return () => controller.abort();
    }, [t]);

    useEffect(() => {
        const container = messageListRef.current;
        if (container) container.scrollTop = container.scrollHeight;
        endOfMessagesRef.current?.scrollIntoView?.({ block: 'end' });
    }, [messages]);

    useEffect(() => {
        onSendingChange?.(isSending);
    }, [isSending, onSendingChange]);

    useEffect(() => () => {
        activeControllerRef.current?.abort();
        objectUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
    }, []);

    const updateAssistant = (assistantId, update) => {
        setMessages((current) => current.map((item) => (item.id === assistantId ? update(item) : item)));
    };

    const addImages = (fileList) => {
        setAttachError('');
        const files = Array.from(fileList || []);
        const accepted = [];
        for (const file of files) {
            if (!IMAGE_TYPES.includes(file.type)) {
                setAttachError(t('chatbot.imageType'));
                continue;
            }
            if (file.size > IMAGE_MAX_BYTES) {
                setAttachError(t('chatbot.imageSize'));
                continue;
            }
            accepted.push(file);
        }
        setAttachments((current) => {
            const room = IMAGE_MAX_COUNT - current.length;
            if (accepted.length > room) setAttachError(t('chatbot.imageCount', { count: IMAGE_MAX_COUNT }));
            const added = accepted.slice(0, Math.max(room, 0)).map((file) => {
                const url = URL.createObjectURL(file);
                objectUrlsRef.current.push(url);
                return { id: makeMessageId(), name: file.name, url };
            });
            return [...current, ...added];
        });
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    const removeImage = (id) => {
        setAttachError('');
        setAttachments((current) => current.filter((item) => item.id !== id));
    };

    const toggleVoice = () => {
        if (speech.listening) speech.stop();
        else speech.start(text);
    };

    const sendMessage = async (event) => {
        event.preventDefault();
        const message = text.trim();
        if (!message || isSending || message.length > MAX_REQUEST_LENGTH) return;
        if (speech.listening) speech.stop();

        setRequestError('');
        setAttachError('');
        setText('');
        setIsSending(true);

        const assistantId = makeMessageId();
        const startedAt = Date.now();
        // Ngôn ngữ của dòng hoạt động theo câu hỏi (vi/en), không theo ngôn ngữ giao diện.
        const activity = { steps: [], phase: 'live', lang: guessLanguage(message), startedAt, endedAt: null };
        const images = attachments;
        setAttachments([]);
        setMessages((current) => [
            ...current,
            { id: makeMessageId(), role: 'user', content: message, images },
            { id: assistantId, role: 'assistant', content: '', activity },
        ]);

        const controller = new AbortController();
        activeControllerRef.current = controller;
        const setActivity = (update) => updateAssistant(assistantId, (item) => (
            item.activity ? { ...item, activity: update(item.activity) } : item
        ));

        try {
            const stream = IS_CRM_TEST ? streamCrmChatbotResponse : streamChatbotResponse;
            await stream(message, {
                userId: IS_CRM_TEST ? CRM_TEST_USER_ID : undefined,
                crmAccessToken: IS_CRM_TEST ? CRM_TEST_TOKEN : undefined,
                signal: controller.signal,
                onStatus: (status) => setActivity((current) => ({ ...current, steps: applyStatus(current.steps, status) })),
                onChunk: (chunk) => {
                    updateAssistant(assistantId, (item) => ({
                        ...item,
                        content: item.content + chunk,
                        // Chữ đầu tiên: thu gọn dòng hoạt động thành một dòng.
                        activity: item.activity && item.activity.phase === 'live' ? { ...item.activity, phase: 'answering' } : item.activity,
                    }));
                },
                onSources: (sources) => updateAssistant(assistantId, (item) => ({ ...item, sources })),
            });
            setActivity((current) => ({ ...current, phase: 'done', endedAt: Date.now() }));
        } catch (error) {
            if (!controller.signal.aborted) {
                setActivity((current) => ({ ...current, phase: 'error', endedAt: Date.now() }));
                if (error?.code === 'request_blocked' && error.message) {
                    updateAssistant(assistantId, (item) => ({ ...item, content: error.message }));
                } else {
                    setRequestError(t('chatbot.sendError'));
                    setMessages((current) => current.filter((item) => (
                        item.id !== assistantId || item.content || item.activity?.steps?.length
                    )));
                }
            }
        } finally {
            if (!controller.signal.aborted) setIsSending(false);
            if (activeControllerRef.current === controller) activeControllerRef.current = null;
        }
    };

    const voiceError = speech.error === 'not-allowed' || speech.error === 'service-not-allowed'
        ? t('chatbot.voiceBlocked')
        : speech.error ? t('chatbot.voiceError') : '';

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
                            <>
                                {message.activity && (
                                    <ActivityTimeline activity={message.activity} />
                                )}
                                {message.content ? (
                                    <>
                                        <Markdown
                                            text={message.content}
                                            renderCitation={(id) => <Citation key={id} id={id} sources={message.sources} />}
                                        />
                                        <SourceList sources={message.sources} />
                                    </>
                                ) : !message.activity && isSending && <span className={styles.typingIndicator}>{t('chatbot.thinking')}</span>}
                            </>
                        ) : (
                            <>
                                {message.images?.length > 0 && (
                                    <div className={styles.userImages}>
                                        {message.images.map((image) => <img key={image.id} src={image.url} alt={image.name} />)}
                                    </div>
                                )}
                                {message.content}
                            </>
                        )}
                    </article>
                ))}
                {requestError && <p className={styles.errorMessage} role="alert">{requestError}</p>}
                <div ref={endOfMessagesRef} />
            </div>

            {attachments.length > 0 && (
                <div className={styles.attachments} aria-label={t('chatbot.attachedImages')}>
                    {attachments.map((image) => (
                        <div key={image.id} className={styles.attachment}>
                            <img src={image.url} alt={image.name} />
                            <button type="button" aria-label={t('chatbot.removeImage', { name: image.name })} onClick={() => removeImage(image.id)}>
                                <X size={12} aria-hidden="true" />
                            </button>
                        </div>
                    ))}
                </div>
            )}
            {(attachError || voiceError) && <p className={styles.composerNote} role="alert">{attachError || voiceError}</p>}
            {speech.listening && <p className={styles.composerNote} role="status">{t('chatbot.listening')}</p>}

            <form className={styles.composer} onSubmit={sendMessage}>
                {IMAGE_INPUT_ENABLED && (
                    <>
                        <input
                            ref={fileInputRef}
                            className={styles.visuallyHidden}
                            type="file"
                            accept={IMAGE_TYPES.join(',')}
                            multiple
                            tabIndex={-1}
                            aria-hidden="true"
                            onChange={(event) => addImages(event.target.files)}
                        />
                        <button
                            className={styles.toolButton}
                            type="button"
                            aria-label={t('chatbot.addImage')}
                            title={t('chatbot.addImage')}
                            disabled={isSending || attachments.length >= IMAGE_MAX_COUNT}
                            onClick={() => fileInputRef.current?.click()}
                        >
                            <ImagePlus size={18} aria-hidden="true" />
                        </button>
                    </>
                )}
                <label className={styles.visuallyHidden} htmlFor="home-chatbot-input">
                    {t('chatbot.messageLabel')}
                </label>
                <input
                    id="home-chatbot-input"
                    className={styles.messageInput}
                    type="text"
                    maxLength={MAX_REQUEST_LENGTH}
                    placeholder={speech.listening ? t('chatbot.listening') : t('chatbot.placeholder')}
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    disabled={isSending}
                />
                {speech.supported && (
                    <button
                        className={`${styles.toolButton} ${speech.listening ? styles.listening : ''}`}
                        type="button"
                        aria-label={speech.listening ? t('chatbot.voiceStop') : t('chatbot.voice')}
                        aria-pressed={speech.listening}
                        title={speech.listening ? t('chatbot.voiceStop') : t('chatbot.voice')}
                        disabled={isSending}
                        onClick={toggleVoice}
                    >
                        {speech.listening ? <Square size={14} aria-hidden="true" /> : <Mic size={18} aria-hidden="true" />}
                    </button>
                )}
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
