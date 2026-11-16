// Shared by the root layout (server) and the theme hook (client).

export const THEME_KEY = "ws-theme";

/**
 * Runs before the page paints (inlined in the root layout), so there's no flash of the
 * wrong theme. Tiny and dependency-free; storage may be blocked, hence the try.
 */
export const THEME_SCRIPT = `try{var t=localStorage.getItem("${THEME_KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;
