// Bộ lọc nằm trên query string để chia sẻ link được (Q26). Chỉ ghi giá trị khác mặc định.

import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

export function parseFilters(searchParams, defaults) {
  const out = {};
  for (const [key, fallback] of Object.entries(defaults)) {
    const value = searchParams.get(key);
    out[key] = value === null ? fallback : value;
  }
  return out;
}

export function filtersToParams(filters, defaults) {
  const params = new URLSearchParams();
  for (const [key, fallback] of Object.entries(defaults)) {
    const value = filters[key];
    if (value !== undefined && value !== null && value !== '' && value !== fallback) params.set(key, String(value));
  }
  return params;
}

export function useUrlFilters(defaults) {
  const [searchParams, setSearchParams] = useSearchParams();
  // defaults là hằng số do màn khai báo; khoá theo JSON để không tạo lại mỗi render.
  const defaultsKey = JSON.stringify(defaults);
  const stableDefaults = useMemo(() => JSON.parse(defaultsKey), [defaultsKey]);
  const filters = useMemo(() => parseFilters(searchParams, stableDefaults), [searchParams, stableDefaults]);

  const setFilters = useCallback(
    (patch) => {
      const next = { ...parseFilters(searchParams, stableDefaults), ...(typeof patch === 'function' ? patch(filters) : patch) };
      setSearchParams(filtersToParams(next, stableDefaults), { replace: true });
    },
    [searchParams, setSearchParams, stableDefaults, filters],
  );

  const resetFilters = useCallback(() => setSearchParams(new URLSearchParams(), { replace: true }), [setSearchParams]);

  return [filters, setFilters, resetFilters];
}
