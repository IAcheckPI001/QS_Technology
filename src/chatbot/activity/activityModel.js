// Dòng hoạt động AI của widget (WU-17 đợt 3A, mock W1/W2 canvas v83).
//
// Backend phát event SSE `status` ở ranh giới từng bước (contract đề xuất, CHƯA có backend; xem
// docs/ai/flows/website-qa/LOG.md 2026-11-25). Mỗi event chỉ gồm mã và số đếm, không có chữ do AI viết:
//   { id, step, state, count?, docs?, score?, models?, intent?, tool?, entities?, rows?, code?, target?, turns? }
//   step:  security | context | analysis | direct | catalog | retrieval | tool | compose | handoff | clarify
//   state: running | done | warn | retry | error | skipped
// Câu hiển thị do file này dịch theo ngôn ngữ của câu hỏi (vi/en; ngôn ngữ khác dùng en). Hàm thuần.

export const LIVE_STATES = new Set(['running']);
const END_STATES = new Set(['done', 'warn', 'retry', 'error', 'skipped']);
const STEPS = new Set(['security', 'context', 'analysis', 'direct', 'catalog', 'retrieval', 'tool', 'compose', 'handoff', 'clarify']);

/** Ngôn ngữ hiển thị theo câu hỏi: có dấu tiếng Việt → vi, còn lại en (quy tắc, không gọi AI). */
export function guessLanguage(text) {
    return /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/i.test(String(text || '')) ? 'vi' : 'en';
}

/** Gộp một event `status` vào danh sách bước (theo `id`; thiếu id thì dùng `step`). Event sai dạng bị bỏ qua. */
export function applyStatus(steps, event, now = Date.now()) {
    if (!event || typeof event !== 'object' || !STEPS.has(event.step)) return steps;
    const state = LIVE_STATES.has(event.state) || END_STATES.has(event.state) ? event.state : 'running';
    const id = typeof event.id === 'string' && event.id ? event.id : event.step;
    const index = steps.findIndex((item) => item.id === id);
    const ended = END_STATES.has(state) ? now : null;
    if (index < 0) {
        return [...steps, { id, step: event.step, state, data: { ...event }, startedAt: now, endedAt: ended }];
    }
    const current = steps[index];
    const next = { ...current, state, data: { ...current.data, ...event }, endedAt: ended ?? current.endedAt };
    return steps.map((item, i) => (i === index ? next : item));
}

const L = {
    vi: {
        starting: 'Đang bắt đầu…',
        thinking: 'Đang soạn câu trả lời…',
        answering: (n) => `Đang trả lời · ${n} bước`,
        processed: (n, s) => `Đã xử lý ${n} bước · ${s} giây`,
        stopped: (n) => `Đã dừng sau ${n} bước`,
        failed: (n) => `Dừng ở bước ${n} do lỗi`,
        noDocs: 'không thấy tài liệu',
        retries: (n) => `${n} lần tự sửa`,
        errors: (n) => `${n} lỗi`,
        seconds: (n) => `${n} giây`,
        slow: 'Đang chờ lâu hơn bình thường',
        slowCrm: 'Đang chờ CRM phản hồi lâu hơn bình thường',
        security: ['Đang kiểm tra an toàn nội dung', 'Kiểm tra an toàn nội dung'],
        securityError: 'Tin nhắn bị chặn ở bước kiểm tra an toàn',
        context: ['Đang đọc lại cuộc trò chuyện', 'Đọc lại cuộc trò chuyện'],
        contextTurns: (n) => `${n} lượt trước`,
        analysis: ['Đang hiểu câu hỏi', 'Hiểu câu hỏi'],
        intent: {
            guide: 'Hướng dẫn sử dụng', lookup: 'Thông tin sản phẩm', compare: 'So sánh sản phẩm',
            troubleshoot: 'Xử lý lỗi', handoff: 'Cần nhân viên hỗ trợ', other: 'Trò chuyện chung', report: 'Báo cáo số liệu',
            record: 'Tra bản ghi',
        },
        compareModels: (n) => `So sánh ${n} model`,
        direct: ['Đang chuẩn bị trả lời', 'Trả lời trực tiếp, không cần tra cứu'],
        catalog: ['Đang tra catalog sản phẩm', 'Tra catalog sản phẩm'],
        retrieval: (target) => (target
            ? [`Đang tìm trong tài liệu ${target}`, `Tìm trong tài liệu ${target}`]
            : ['Đang tìm trong tài liệu', 'Tìm trong tài liệu']),
        found: (n, score) => `Tìm thấy ${n} đoạn${score ? ` · độ khớp cao nhất ${score}/10` : ''}`,
        notFound: 'Không có đoạn nào đủ khớp',
        crmSchema: ['Đang xem cấu trúc dữ liệu CRM', 'Xem cấu trúc dữ liệu CRM'],
        crmQuery: (entity) => (entity
            ? [`Đang lấy dữ liệu ${entity.toLowerCase()}`, `Lấy dữ liệu ${entity.toLowerCase()}`]
            : ['Đang lấy dữ liệu từ CRM', 'Lấy dữ liệu từ CRM']),
        docsTool: ['Đang tìm trong tài liệu sản phẩm', 'Tìm trong tài liệu sản phẩm'],
        toolOther: ['Đang dùng công cụ', 'Dùng công cụ'],
        rows: (n) => `Nhận ${n} dòng dữ liệu`,
        retry: 'Truy vấn chưa đúng · đang thử lại',
        retried: 'Truy vấn chưa đúng, AI đã tự sửa',
        attempt: (n) => ` (lần ${n})`,
        compose: ['Đang soạn câu trả lời', 'Soạn câu trả lời'],
        basedOn: (n) => `Dựa trên ${n} nguồn`,
        noSources: 'Không có nguồn để trích dẫn',
        handoff: ['Đang chuyển nhân viên hỗ trợ', 'Chuyển nhân viên hỗ trợ'],
        clarify: ['Đang xem cần hỏi thêm gì', 'Cần hỏi lại để làm rõ'],
        stoppedStep: 'đã dừng',
        error: {
            crm_forbidden: 'Tài khoản của bạn không có quyền xem dữ liệu này trên CRM. Cần phân quyền trên CRM.',
            crm_auth_failed: 'CRM từ chối đăng nhập (phiên CRM sai hoặc hết hạn). Hãy đăng nhập lại CRM.',
            crm_unavailable: 'Không lấy được dữ liệu từ CRM (CRM không phản hồi hoặc trả lỗi).',
            crm_user_missing: 'Hội thoại không gắn với nhân viên CRM nên không được đọc dữ liệu.',
            tool_timeout: 'Bước này chạy quá thời gian cho phép.',
            tool_call_limit: 'Đã gọi công cụ quá số lần cho phép, hệ thống dừng lại.',
            crm_query_invalid: 'CRM từ chối truy vấn.',
            tool_invalid_args: 'AI dựng truy vấn chưa đúng.',
            default: 'Bước này gặp lỗi.',
        },
    },
    en: {
        starting: 'Getting started…',
        thinking: 'Preparing a reply…',
        answering: (n) => `Answering · ${n} steps`,
        processed: (n, s) => `Processed ${n} steps · ${s} s`,
        stopped: (n) => `Stopped after ${n} steps`,
        failed: (n) => `Stopped at step ${n} because of an error`,
        noDocs: 'no documents found',
        retries: (n) => `${n} self-correction${n > 1 ? 's' : ''}`,
        errors: (n) => `${n} error${n > 1 ? 's' : ''}`,
        seconds: (n) => `${n} s`,
        slow: 'Taking longer than usual',
        slowCrm: 'Waiting for the CRM longer than usual',
        security: ['Running safety check', 'Safety check'],
        securityError: 'Message blocked by the safety check',
        context: ['Reading the conversation', 'Read the conversation'],
        contextTurns: (n) => `${n} earlier turns`,
        analysis: ['Understanding your question', 'Understood your question'],
        intent: {
            guide: 'How-to guide', lookup: 'Product information', compare: 'Product comparison',
            troubleshoot: 'Troubleshooting', handoff: 'Needs a support agent', other: 'General chat', report: 'Data report',
            record: 'Record lookup',
        },
        compareModels: (n) => `Comparing ${n} models`,
        direct: ['Preparing a reply', 'Answered directly, no search needed'],
        catalog: ['Checking the product catalog', 'Checked the product catalog'],
        retrieval: (target) => (target
            ? [`Searching ${target} documents`, `Searched ${target} documents`]
            : ['Searching documents', 'Searched documents']),
        found: (n, score) => `Found ${n} passage${n > 1 ? 's' : ''}${score ? ` · best match ${score}/10` : ''}`,
        notFound: 'No passage matched well enough',
        crmSchema: ['Checking the CRM data structure', 'Checked the CRM data structure'],
        crmQuery: (entity) => (entity ? [`Fetching ${entity}`, `Fetched ${entity}`] : ['Fetching CRM data', 'Fetched CRM data']),
        docsTool: ['Searching product documents', 'Searched product documents'],
        toolOther: ['Using a tool', 'Used a tool'],
        rows: (n) => `Received ${n} row${n > 1 ? 's' : ''}`,
        retry: 'Query was not valid · retrying',
        retried: 'Query was not valid, the assistant corrected it',
        attempt: (n) => ` (attempt ${n})`,
        compose: ['Writing the answer', 'Wrote the answer'],
        basedOn: (n) => `Based on ${n} source${n > 1 ? 's' : ''}`,
        noSources: 'No sources to cite',
        handoff: ['Handing over to a support agent', 'Handed over to a support agent'],
        clarify: ['Checking what to ask', 'Needs a clarifying question'],
        stoppedStep: 'stopped',
        error: {
            crm_forbidden: 'Your account is not allowed to see this data in the CRM.',
            crm_auth_failed: 'The CRM rejected the sign-in. Please sign in to the CRM again.',
            crm_unavailable: 'Could not get data from the CRM.',
            crm_user_missing: 'This conversation is not linked to a CRM employee.',
            tool_timeout: 'This step took too long.',
            tool_call_limit: 'The tool was called too many times, so the assistant stopped.',
            crm_query_invalid: 'The CRM rejected the query.',
            tool_invalid_args: 'The assistant built an invalid query.',
            default: 'This step failed.',
        },
    },
};

export const strings = (lang) => L[lang] || L.en;

const num = (value, lang, digits = 1) => Number(value).toLocaleString(lang === 'vi' ? 'vi-VN' : 'en-US', {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
});

const intentGroup = (intent) => String(intent || '').split('.')[0];

/** Chữ và chi tiết của một bước theo trạng thái: { label, detail, chips[{text,kind}], tone }. */
export function describeStep(item, lang, attempt = 1) {
    const S = strings(lang);
    const d = item.data || {};
    const running = item.state === 'running';
    const pick = (pair) => (running ? `${pair[0]}…` : pair[1]);
    const chips = [];
    let label;
    let detail = '';
    switch (item.step) {
        case 'security':
            label = item.state === 'error' ? S.securityError : pick(S.security);
            break;
        case 'context':
            label = pick(S.context);
            if (!running && d.turns) detail = S.contextTurns(d.turns);
            break;
        case 'analysis': {
            label = pick(S.analysis);
            const models = Array.isArray(d.models) ? d.models : [];
            if (!running) {
                const group = intentGroup(d.intent);
                detail = group === 'compare' && models.length > 1 ? S.compareModels(models.length) : S.intent[group] || '';
                models.forEach((model) => chips.push({ text: model, kind: 'model' }));
            }
            break;
        }
        case 'direct': label = pick(S.direct); break;
        case 'catalog': label = pick(S.catalog); break;
        case 'retrieval':
            label = pick(S.retrieval(d.target));
            if (item.state === 'warn' || (!running && d.count === 0)) detail = S.notFound;
            else if (!running && d.count) detail = S.found(d.count, typeof d.score === 'number' ? num(d.score * 10, lang) : '');
            break;
        case 'tool': {
            const entities = Array.isArray(d.entities) ? d.entities : [];
            if (d.tool === 'crm_schema') label = pick(S.crmSchema);
            else if (d.tool === 'crm_query') label = pick(S.crmQuery(entities[0]));
            else if (d.tool === 'product_docs_ask') label = pick(S.docsTool);
            else label = pick(S.toolOther);
            if (attempt > 1) label += S.attempt(attempt);
            if (item.state === 'retry') detail = running ? S.retry : S.retried;
            else if (item.state === 'error') detail = S.error[d.code] || S.error.default;
            else if (!running && typeof d.rows === 'number') detail = S.rows(d.rows);
            else if (!running && d.tool === 'product_docs_ask' && d.count) {
                detail = S.found(d.count, typeof d.score === 'number' ? num(d.score * 10, lang) : '');
            }
            if (d.tool === 'crm_schema' || (d.tool === 'crm_query' && item.state === 'error')) {
                entities.forEach((entity) => chips.push({ text: entity, kind: 'table' }));
            }
            break;
        }
        case 'compose':
            label = pick(S.compose);
            if (!running && typeof d.count === 'number') detail = d.count > 0 ? S.basedOn(d.count) : S.noSources;
            break;
        case 'handoff': label = pick(S.handoff); break;
        case 'clarify': label = pick(S.clarify); break;
        default: label = '';
    }
    if (item.step !== 'tool' && item.state === 'error' && !detail) detail = S.error[d.code] || S.error.default;
    if (item.state === 'skipped') label = `${label.replace(/…$/, '')} · ${S.stoppedStep}`;
    if (item.step === 'retrieval' || (item.step === 'tool' && d.tool === 'product_docs_ask')) {
        if (!running && Array.isArray(d.docs)) d.docs.forEach((doc) => chips.push({ text: doc, kind: 'doc' }));
    }
    return { label, detail, chips };
}

/** Số lần gọi lặp của cùng một công cụ CRM (để ghi "lần 2"). */
export function attempts(steps) {
    const seen = {};
    return steps.map((item) => {
        if (item.step !== 'tool') return 1;
        const key = `${item.data?.tool}:${(item.data?.entities || [])[0] || ''}`;
        seen[key] = (seen[key] || 0) + 1;
        return seen[key];
    });
}

/**
 * Dòng tóm tắt: { text, tone } theo pha. phase: live | answering | done | stopped | error.
 * tone: ok | warn | error | muted.
 */
export function summarize(steps, phase, lang, elapsedMs) {
    const S = strings(lang);
    const n = steps.length;
    const warn = steps.some((item) => item.state === 'warn');
    const retries = steps.filter((item) => item.state === 'retry').length;
    const errors = steps.filter((item) => item.state === 'error').length;
    if (phase === 'stopped') return { text: S.stopped(steps.filter((s) => s.state !== 'skipped' && s.state !== 'running').length), tone: 'muted' };
    if (phase === 'error') return { text: S.failed(n), tone: 'error' };
    if (phase === 'answering') return { text: S.answering(n), tone: 'live' };
    if (phase !== 'done') {
        const current = [...steps].reverse().find((item) => item.state === 'running');
        return { text: current ? describeStep(current, lang).label : S.starting, tone: 'live' };
    }
    const parts = [S.processed(n, num(Math.max(elapsedMs, 0) / 1000, lang))];
    if (warn) parts.push(S.noDocs);
    if (retries) parts.push(S.retries(retries));
    if (errors) parts.push(S.errors(errors));
    return { text: parts.join(' · '), tone: errors ? 'error' : warn ? 'warn' : 'ok' };
}

/** Mở sẵn sau khi trả lời khi có cảnh báo/lỗi, để khách hiểu vì sao câu trả lời thiếu. */
export const openByDefault = (steps) => steps.some((item) => item.state === 'warn' || item.state === 'error');
