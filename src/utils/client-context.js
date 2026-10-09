

export function getClientContext() {
  return {
    locale: (localStorage.getItem("language") || navigator.language || null),
    timezone:
      Intl.DateTimeFormat().resolvedOptions().timeZone || null,
    page_url: window.location.href || null,
  };
}