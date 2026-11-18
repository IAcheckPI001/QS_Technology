// Tải một tài nguyên: huỷ request cũ khi deps đổi hoặc component gỡ, có reload để "Thử lại".

import { useCallback, useEffect, useRef, useState } from 'react';

export function useResource(loader, deps = []) {
  const [state, setState] = useState({ data: undefined, error: null, loading: true });
  const [nonce, setNonce] = useState(0);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  useEffect(() => {
    const controller = new AbortController();
    setState((prev) => ({ ...prev, error: null, loading: true }));
    loaderRef.current({ signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setState({ data, error: null, loading: false });
      })
      .catch((error) => {
        if (controller.signal.aborted || (error && error.kind === 'aborted')) return;
        setState((prev) => ({ ...prev, error, loading: false }));
      });
    return () => controller.abort();
    // deps do nơi gọi truyền vào; loader đọc qua ref để không phải liệt kê.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { ...state, reload };
}
