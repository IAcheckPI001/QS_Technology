

import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import Chatbot from '../chatbot/Chatbot.jsx';
import aiIcon from '../assets/icon/ai-icon.svg';
import styles from '../chatbot/Chatbot.module.css';

function ChatbotWidget () {
    const [isOpen, setIsOpen] = useState(false);
    const [hasOpened, setHasOpened] = useState(false);
    const [isThinking, setIsThinking] = useState(false);
    const toggleRef = useRef(null);
    const { t } = useTranslation();

    const closeWidget = () => {
        setIsOpen(false);
        window.requestAnimationFrame(() => toggleRef.current?.focus());
    };

    useEffect(() => {
        if (!isOpen) return undefined;

        const handleKeyDown = (event) => {
            if (event.key === 'Escape') closeWidget();
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isOpen]);

    return (
        <div className={styles.widgetRoot}>
            {hasOpened && (
                <Chatbot
                    hidden={!isOpen}
                    closeWinChatbot={closeWidget}
                    onSendingChange={setIsThinking}
                />
            )}
            <button
                ref={toggleRef}
                className={`${styles.widgetToggle} ${isThinking && !isOpen ? styles.isThinking : ''}`}
                type="button"
                aria-expanded={isOpen}
                aria-controls="home-chatbot-panel"
                aria-label={t('chatbot.open')}
                aria-busy={isThinking && !isOpen}
                onClick={() => {
                    if (!isOpen) setHasOpened(true);
                    setIsOpen((open) => !open);
                }}
                hidden={isOpen}
            >
                <img className={styles.widgetIcon} src={aiIcon} alt="" aria-hidden="true" />
                {isThinking && !isOpen && (
                    <span className={styles.thinkingBubble} aria-hidden="true">
                        <span />
                        <span />
                        <span />
                    </span>
                )}
                <span className={styles.visuallyHidden} role="status" aria-live="polite">
                    {isThinking && !isOpen ? t('chatbot.thinking') : ''}
                </span>
            </button>
        </div>
    );
}

export default ChatbotWidget;
