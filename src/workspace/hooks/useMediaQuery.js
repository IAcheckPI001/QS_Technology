// Theo dõi media query (vd. bố cục điện thoại ≤ 720px) để đổi cách trình bày, không đổi dữ liệu.

import { useEffect, useState } from 'react';

function matches(query) {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function' ? window.matchMedia(query).matches : false;
}

export function useMediaQuery(query) {
  const [value, setValue] = useState(() => matches(query));
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined;
    const list = window.matchMedia(query);
    const update = () => setValue(list.matches);
    update();
    list.addEventListener('change', update);
    return () => list.removeEventListener('change', update);
  }, [query]);
  return value;
}

export const PHONE_QUERY = '(max-width: 720px)';
