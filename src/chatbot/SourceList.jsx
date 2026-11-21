import styles from './Chatbot.module.css';

// Chỉ nhận URL https do backend ký (Supabase Storage); bỏ mọi giá trị khác.
const isSafeUrl = (url) => typeof url === 'string' && url.startsWith('https://');

const pageLabel = (pages) => (pages ? ` · tr. ${pages}` : '');

export default function SourceList({ sources }) {
    if (!Array.isArray(sources) || sources.length === 0) return null;
    return (
        <div className={styles.sourceList}>
            {sources.map((source) => {
                const images = (source.images || []).filter((image) => isSafeUrl(image.url));
                return (
                    <section className={styles.sourceItem} key={source.source_id}>
                        <p className={styles.sourceTitle}>
                            <span className={styles.sourceChip}>{source.source_id}</span>
                            {source.title}{pageLabel(source.pages)}
                        </p>
                        {images.length > 0 && (
                            <div className={styles.sourceImages}>
                                {images.map((image) => (
                                    <a
                                        key={image.url}
                                        href={image.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        aria-label={`${source.title}, trang ${image.page ?? ''}`}
                                    >
                                        <img
                                            src={image.url}
                                            alt={`${source.title}${image.page ? `, trang ${image.page}` : ''}`}
                                            loading="lazy"
                                            referrerPolicy="no-referrer"
                                        />
                                    </a>
                                ))}
                            </div>
                        )}
                    </section>
                );
            })}
        </div>
    );
}
