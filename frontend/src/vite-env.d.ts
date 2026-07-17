/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API origin override for deployments (e.g. "https://api.example.com"). Empty = same origin. */
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
