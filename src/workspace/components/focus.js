// Tìm phần tử nhận focus được trong một vùng (giữ focus trong cửa sổ, 18.3).

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function focusableIn(node) {
  return node ? [...node.querySelectorAll(FOCUSABLE)].filter((el) => !el.hasAttribute('hidden')) : [];
}
