// Nghĩa của lỗi công cụ (CRM, tra tài liệu) cho người dùng không chuyên kỹ thuật, và kết luận lượt CRM có
// lấy được số liệu không. Hàm thuần.
// - Cùng mã có thể mang nghĩa khác theo công cụ: tra "<tool>:<mã>" trước, rồi "<mã>".
// - Đọc `agent_steps` theo thứ tự (B5): lỗi được coi là "đã tự sửa" khi cùng công cụ có lần gọi
//   thành công sau đó. Không có `agent_steps` thì chỉ đếm theo `sources.tools`.

import { S } from '../../strings.vi.js';

// "deduplicated" dùng lại kết quả của lần gọi trùng trước đó (có thể là lần lỗi): đếm riêng, không tính
// là thành công hay đã tự sửa.
const OK = 'ok';
const DUPLICATE = 'deduplicated';
const DOCS_TOOL = 'product_docs_ask';
const QUERY_TOOL = 'crm_query';

export function toolErrorInfo(tool, code) {
  const table = S.trace.toolError;
  const info = table[`${tool}:${code}`] || table[code] || table.unknown;
  return { code, ...info };
}

export function toolLabel(tool) {
  return S.trace.spans[`tool.${tool}`] || tool;
}

function rowsFromSteps(steps) {
  const rows = new Map();
  const toolSteps = steps.filter((step) => step && step.kind === 'tool' && step.name && step.name !== DOCS_TOOL);
  toolSteps.forEach((step, index) => {
    if (!rows.has(step.name)) rows.set(step.name, { name: step.name, calls: 0, ok: 0, duplicate: 0, failed: 0, recovered: 0, reasons: new Map() });
    const row = rows.get(step.name);
    row.calls += 1;
    if (step.status === OK) {
      row.ok += 1;
      return;
    }
    if (step.status === DUPLICATE) {
      row.duplicate += 1;
      return;
    }
    row.failed += 1;
    const laterSuccess = toolSteps.slice(index + 1).some((later) => later.name === step.name && later.status === OK);
    if (laterSuccess) row.recovered += 1;
    const code = step.status || 'unknown';
    row.reasons.set(code, (row.reasons.get(code) || 0) + 1);
  });
  return [...rows.values()];
}

function rowsFromSources(tools) {
  return tools.map((tool) => ({
    name: tool.name,
    calls: tool.calls || 0,
    ok: Math.max((tool.calls || 0) - (tool.failed || 0), 0),
    duplicate: 0,
    failed: tool.failed || 0,
    recovered: null, // không biết thứ tự gọi
    reasons: new Map(Object.entries(tool.errors || {})),
  }));
}

function resultText(row) {
  if (row.failed === 0 && row.duplicate === 0) return S.conv.src.callsAllOk(row.calls);
  if (row.ok === 0 && row.duplicate === 0) return S.conv.src.callsAllFailed(row.calls);
  return S.conv.src.callsMixed(row.calls, row.ok, row.failed, row.recovered || 0, row.duplicate);
}

/**
 * Phân tích công cụ của một lượt.
 * @returns {{ rows, verdict: { tone: 'success'|'warning'|'neutral', title, detail } | null, ordered: boolean }}
 */
export function analyzeTools(agentSteps, sources) {
  const ordered = Array.isArray(agentSteps) && agentSteps.some((step) => step?.kind === 'tool');
  const raw = ordered ? rowsFromSteps(agentSteps) : rowsFromSources(sources?.tools || []);
  const rows = raw.map((row) => ({
    ...row,
    label: toolLabel(row.name),
    result: resultText(row),
    reasons: [...row.reasons.entries()].map(([code, count]) => ({ ...toolErrorInfo(row.name, code), count })),
  }));
  if (!rows.length) return { rows, verdict: null, ordered };

  const failed = rows.reduce((sum, row) => sum + row.failed, 0);
  const recovered = rows.reduce((sum, row) => sum + (row.recovered || 0), 0);
  const query = rows.find((row) => row.name === QUERY_TOOL);
  let verdict;
  if (query && query.ok > 0) {
    verdict = { tone: 'success', title: S.conv.src.verdictOk, detail: recovered ? S.conv.src.verdictRecovered(recovered) : '' };
  } else if (query || failed > 0) {
    verdict = { tone: 'warning', title: S.conv.src.verdictFail, detail: '' };
  } else {
    verdict = { tone: 'neutral', title: S.conv.src.verdictSchemaOnly, detail: '' };
  }
  return { rows, verdict, ordered };
}
