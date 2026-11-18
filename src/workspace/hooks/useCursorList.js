// Danh sách phân trang con trỏ (Q26): tải trang đầu khi `key` (bộ lọc) đổi, "Tải thêm" nối trang kế,
// đổi bộ lọc thì bỏ các trang cũ và tải lại từ đầu. fetchPage({ cursor, signal }) trả
// { items, next_cursor, total? }.

import { useCallback, useEffect, useRef, useState } from 'react';

const INITIAL = { items: [], nextCursor: null, total: null, loading: true, loadingMore: false, error: null, done: false };

export function useCursorList(fetchPage, key) {
  const [state, setState] = useState(INITIAL);
  const fetchRef = useRef(fetchPage);
  fetchRef.current = fetchPage;
  const controllerRef = useRef(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    inFlightRef.current = false;
    setState(INITIAL);
    fetchRef.current({ cursor: null, signal: controller.signal })
      .then((page) => {
        if (controller.signal.aborted) return;
        const next = page.next_cursor || null;
        setState({ items: page.items || [], nextCursor: next, total: page.total ?? null, loading: false, loadingMore: false, error: null, done: !next });
      })
      .catch((error) => {
        if (controller.signal.aborted || error?.kind === 'aborted') return;
        setState({ ...INITIAL, loading: false, error });
      });
    return () => controller.abort();
  }, [key, nonce]);

  // Đọc state mới nhất qua ref; inFlight chặn bấm "Tải thêm" liên tiếp trước khi kịp render lại.
  const stateRef = useRef(state);
  stateRef.current = state;
  const inFlightRef = useRef(false);

  const loadMore = useCallback(() => {
    const prev = stateRef.current;
    if (inFlightRef.current || prev.loading || prev.done || !prev.nextCursor) return;
    inFlightRef.current = true;
    const controller = controllerRef.current;
    setState((cur) => ({ ...cur, loadingMore: true, error: null }));
    fetchRef.current({ cursor: prev.nextCursor, signal: controller?.signal })
      .then((page) => {
        if (controller?.signal.aborted) return;
        const next = page.next_cursor || null;
        setState((cur) => ({
          ...cur,
          items: [...cur.items, ...(page.items || [])],
          nextCursor: next,
          total: page.total ?? cur.total,
          loadingMore: false,
          error: null,
          done: !next,
        }));
      })
      .catch((error) => {
        if (controller?.signal.aborted || error?.kind === 'aborted') return;
        // Lỗi khi tải thêm: giữ dữ liệu đã có, cho "Thử lại".
        setState((cur) => ({ ...cur, loadingMore: false, error }));
      })
      .finally(() => {
        inFlightRef.current = false;
      });
  }, []);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { ...state, loadMore, reload };
}
