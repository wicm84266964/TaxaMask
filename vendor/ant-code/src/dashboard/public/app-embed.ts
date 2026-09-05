export function applyTaxaMaskEmbedMode(search: string = globalThis.location?.search ?? "") {
  const params = new URLSearchParams(search);
  if (!params.has("taxamask_embed")) {
    return false;
  }
  const root = globalThis.document?.documentElement;
  const body = globalThis.document?.body;
  const theme = String(params.get("taxamask_theme") || "").trim().toLowerCase();
  root?.classList.add("taxamask-embed");
  root?.classList.remove("taxamask-embed-light", "taxamask-embed-dark");
  if (theme === "light" || theme === "dark") {
    root?.classList.add(`taxamask-embed-${theme}`);
    if (root?.style) {
      root.style.colorScheme = theme;
    }
  }
  body?.classList.add("taxamask-embed-body");
  return true;
}
