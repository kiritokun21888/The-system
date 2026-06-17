/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DEV_SERVER?: string;
  readonly VITE_WS_URL?: string;
  readonly VITE_API_URL?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Bridge exposed by electron/preload.js (optional at runtime).
interface Window {
  swarmAPI?: {
    minimize: () => void;
    maximize: () => void;
    close: () => void;
    onNavigate: (cb: (view: string) => void) => void;
  };
}
