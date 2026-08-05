// Ambient Vite types, declared locally instead of via `types: ["vite/client"]`.
// The template is committed without node_modules, so naming vite/client as a type
// library made tsc (and every editor opening the template) fail to resolve it until
// npm install had run. Shape mirrors vite/client for the parts scaffolds touch.

interface ImportMetaEnv {
  readonly BASE_URL: string;
  readonly MODE: string;
  readonly DEV: boolean;
  readonly PROD: boolean;
  readonly SSR: boolean;
  readonly VITE_API_URL?: string;
  readonly VITE_API_KEY_HEADER?: string;
  readonly VITE_ADMIN_API_KEY_HEADER?: string;
  readonly [key: string]: any;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "*.css";
