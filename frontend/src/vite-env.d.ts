/** The API's origin for the dev server, which serves the page from its own (§9.8); unset in a
 * build, so the page calls the origin that served it. */
interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
