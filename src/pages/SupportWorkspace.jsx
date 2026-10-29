import { useEffect, useMemo, useState } from 'react';
import {
    ChevronRight,
    Filter,
    Layers3,
    LoaderCircle,
    MessageCircle,
    Search,
    Ticket,
} from 'lucide-react';
import {
    getRetrievalSnapshot,
    listChatConversations,
} from '../services/chatbot.service.js';
import styles from '../assets/css/SupportWorkspace.module.css';
import Chat from './Chat.jsx';
import ChatbotWidget from '../components/ChatbotWidget.jsx';

const SESSION_ID_KEY = 'chatbot_session_id';
const SEARCH_DEBOUNCE_MS = 300;

const STATUS_LABELS = {
    completed: 'Đang mở',
    blocked: 'Bị chặn',
    error: 'Lỗi hệ thống',
    cancelled: 'Khách ngắt kết nối',
};
const CHANNEL_LABELS = { website: 'Website', crm: 'CRM' };

const NAV_ITEMS = [
    { key: 'ticket', label: 'Hỗ trợ ticket', Icon: Ticket },
    { key: 'chunks', label: 'Kết quả chunk', Icon: Layers3 },
    { key: 'history', label: 'Lịch sử hội thoại', Icon: MessageCircle },
];

function readStoredSessionId() {
    try {
        return localStorage.getItem(SESSION_ID_KEY) || '';
    } catch {
        return '';
    }
}

// dd/MM/yyyy - HH:mm (Intl vi-VN đặt giờ trước ngày nên tự ghép).
function formatDate(value) {
    if (!value) return '-';
    const date = new Date(value);
    const pad = (number) => String(number).padStart(2, '0');
    return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()} - ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function formatNumber(value) {
    return new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 0 }).format(value || 0);
}

function ViewHeading({ title, description }) {
    return (
        <div className={styles.viewHeading}>
            <h1>{title}</h1>
            <p>{description}</p>
        </div>
    );
}

function TicketSupport({ sessionId, onSessionChange }) {
    return (
        <section>
            <ViewHeading title="Hỗ trợ ticket" description="Tiếp nhận, xử lý và phản hồi yêu cầu hỗ trợ kỹ thuật" />
            <div className={styles.ticketPanel}>
                <Chat sessionId={sessionId} onSessionChange={onSessionChange} />
            </div>
        </section>
    );
}

function ChunkResults({ sessionId }) {
    const [snapshot, setSnapshot] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        setSnapshot(null);
        setError('');
        if (!sessionId) return undefined;
        const controller = new AbortController();
        setLoading(true);
        getRetrievalSnapshot(sessionId, { signal: controller.signal })
            .then((data) => {
                if (!controller.signal.aborted) setSnapshot(data);
            })
            .catch((requestError) => {
                if (controller.signal.aborted || requestError?.response?.status === 404) return;
                setError(requestError?.response?.data?.detail?.message || 'Không thể tải kết quả truy xuất.');
            })
            .finally(() => {
                if (!controller.signal.aborted) setLoading(false);
            });
        return () => controller.abort();
    }, [sessionId]);

    const chunks = snapshot?.chunks || [];
    const models = snapshot?.product_models?.length ? snapshot.product_models.join(', ') : '-';

    return (
        <section>
            <ViewHeading title="Kết quả Chunk" />
            <div className={styles.queryCard}>
                <div>
                    <small>Tin nhắn người dùng</small>
                    <strong>{snapshot?.query || 'Chưa có dữ liệu truy xuất'}</strong>
                </div>
                <span className={styles.modelBadge}>Model: {models}</span>
            </div>
            <div className={styles.metrics}>
                <div>
                    <small>ĐIỂM CAO NHẤT</small>
                    <strong className={styles.accent}>{snapshot?.highest_score != null ? snapshot.highest_score.toFixed(2) : '-'}</strong>
                    <span>Chunk xếp hạng #1</span>
                </div>
                <div>
                    <small>THỜI GIAN</small>
                    <strong>{snapshot?.latency_ms ?? '-'} ms</strong>
                    <span>Thời gian truy xuất</span>
                </div>
                <div>
                    <small>TỔNG SỐ TOKEN</small>
                    <strong>{formatNumber(snapshot?.total_tokens)}</strong>
                    <span>tokens</span>
                </div>
            </div>
            <div className={styles.tableCard}>
                {loading ? <LoaderCircle className={styles.spin} aria-label="Đang tải" /> : (
                    <div className={styles.tableScroll}>
                        <table>
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Score</th>
                                    <th>Nội dung chunk</th>
                                    <th>domain</th>
                                    <th>scopes</th>
                                    <th>control_interface</th>
                                    <th>spec_attributes</th>
                                    <th>Số trang</th>
                                </tr>
                            </thead>
                            <tbody>
                                {chunks.map((chunk) => (
                                    <tr key={chunk.rank}>
                                        <td className={styles.rank}>{chunk.rank}</td>
                                        <td className={styles.score}>{chunk.score.toFixed(2)}</td>
                                        <td className={styles.chunkContent}>{chunk.content}</td>
                                        <td>{chunk.domain || '-'}</td>
                                        <td>{chunk.scopes.join(', ') || '-'}</td>
                                        <td>{chunk.control_interface.join(', ') || '-'}</td>
                                        <td>{chunk.spec_attributes.join(', ') || '-'}</td>
                                        <td>{chunk.page_label || '-'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        {!chunks.length && (
                            <div className={error ? styles.error : styles.emptyState}>
                                {error || 'Chưa có kết quả truy xuất cho hội thoại này.'}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </section>
    );
}

function Conversations({ onSelect }) {
    const [data, setData] = useState({ conversations: [] });
    const [search, setSearch] = useState('');
    const [debouncedSearch, setDebouncedSearch] = useState('');
    const [status, setStatus] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        const timer = setTimeout(() => setDebouncedSearch(search.trim()), SEARCH_DEBOUNCE_MS);
        return () => clearTimeout(timer);
    }, [search]);

    useEffect(() => {
        const controller = new AbortController();
        setLoading(true);
        setError('');
        listChatConversations(
            { search: debouncedSearch || undefined, status: status || undefined },
            { signal: controller.signal },
        )
            .then((result) => {
                if (!controller.signal.aborted) setData(result);
            })
            .catch((requestError) => {
                if (controller.signal.aborted) return;
                setData({ conversations: [] });
                setError(requestError?.response?.data?.detail?.message || 'Không thể tải lịch sử hội thoại.');
            })
            .finally(() => {
                if (!controller.signal.aborted) setLoading(false);
            });
        return () => controller.abort();
    }, [debouncedSearch, status]);

    const cost = useMemo(() => formatNumber(data.total_cost_vnd), [data.total_cost_vnd]);
    const conversations = data.conversations || [];

    return (
        <section>
            <ViewHeading title="Lịch sử hội thoại" description="Lịch sử hỗ trợ tại website và crm" />
            <div className={styles.metrics}>
                <div>
                    <small>SỐ HỘI THOẠI</small>
                    <strong>{formatNumber(data.conversation_count)}</strong>
                    <span>hội thoại</span>
                </div>
                <div>
                    <small>SỐ LẦN HANDOFF</small>
                    <strong className={styles.accent}>{formatNumber(data.handoff_count)}</strong>
                    <span>hội thoại</span>
                </div>
                <div>
                    <small>TỔNG CHI PHÍ</small>
                    <strong className={styles.cost}>{cost}</strong>
                    <span>đồng</span>
                </div>
            </div>
            <div className={styles.tableCard}>
                <div className={styles.tableHeader}>
                    <h2>Tất cả hội thoại</h2>
                    <label>
                        <Search size={16} aria-hidden="true" />
                        <input
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                            placeholder="Tìm ticket, model, nội dung"
                            aria-label="Tìm hội thoại"
                        />
                    </label>
                    <label>
                        <Filter size={16} aria-hidden="true" />
                        <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Lọc theo trạng thái">
                            <option value="">Tất cả trạng thái</option>
                            {Object.entries(STATUS_LABELS).map(([value, label]) => (
                                <option key={value} value={value}>{label}</option>
                            ))}
                        </select>
                    </label>
                </div>
                {loading ? <LoaderCircle className={styles.spin} aria-label="Đang tải" /> : (
                    <div className={styles.tableScroll}>
                        <table>
                            <thead>
                                <tr>
                                    <th>Ticket/Model</th>
                                    <th>Kênh</th>
                                    <th>Ngày bắt đầu</th>
                                    <th>Ngày nhắn cuối</th>
                                    <th>Trạng thái</th>
                                    <th aria-label="Mở hội thoại" />
                                </tr>
                            </thead>
                            <tbody>
                                {conversations.map((item) => (
                                    <tr key={item.session_id} onClick={() => onSelect(item.session_id)}>
                                        <td>
                                            <strong>{item.product_models?.join(', ') || item.model || 'Chatbot'}</strong>
                                            {item.ticket_id && <small>#{item.ticket_id}</small>}
                                            <small>{item.last_query}</small>
                                        </td>
                                        <td>{CHANNEL_LABELS[item.channel] || item.channel}</td>
                                        <td>{formatDate(item.created_at)}</td>
                                        <td>{formatDate(item.updated_date)}</td>
                                        <td>
                                            <span className={`${styles.status} ${styles[`status-${item.status}`] || ''}`}>
                                                {STATUS_LABELS[item.status] || item.status}
                                            </span>
                                        </td>
                                        <td className={styles.chevron}><ChevronRight size={18} aria-hidden="true" /></td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        {!conversations.length && (
                            <div className={error ? styles.error : styles.emptyState}>{error || 'Chưa có hội thoại.'}</div>
                        )}
                    </div>
                )}
            </div>
        </section>
    );
}

export default function SupportWorkspace() {
    const [active, setActive] = useState('ticket');
    // Session đang xem chung cho cả 3 mục; khởi tạo từ phiên chatbot gần nhất của trình duyệt.
    const [sessionId, setSessionId] = useState(readStoredSessionId);

    const selectConversation = (id) => {
        setSessionId(id);
        setActive('ticket');
    };

    return (
        <main className={styles.workspace}>
            <aside className={styles.sidebar}>
                <div className={styles.brand}>WORKSPACE</div>
                {NAV_ITEMS.map((item) => {
                    const Icon = item.Icon;
                    return (
                        <button
                            type="button"
                            key={item.key}
                            className={active === item.key ? styles.activeItem : ''}
                            aria-current={active === item.key ? 'page' : undefined}
                            onClick={() => setActive(item.key)}
                        >
                            <Icon size={18} aria-hidden="true" />
                            {item.label}
                        </button>
                    );
                })}
                <div className={styles.sidebarFooter}>
                    <strong>QS Technology</strong>
                    <small>Support workspace · Demo</small>
                </div>
            </aside>
            <div className={styles.content}>
                {active === 'ticket' && <TicketSupport sessionId={sessionId} onSessionChange={setSessionId} />}
                {active === 'chunks' && <ChunkResults sessionId={sessionId} />}
                {active === 'history' && <Conversations onSelect={selectConversation} />}
            </div>
            {/* Render ngoài các mục để widget không unmount khi đổi mục. */}
            <ChatbotWidget />
        </main>
    );
}
