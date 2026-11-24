"use strict";

// El UMD de @xyflow/react espera un global jsxRuntime (react/jsx-runtime), que React 18 no publica como UMD.
// jsx(type, props, key) equivale a createElement con la clave dentro de props. Fichero propio y no inline,
// porque la CSP default-src 'self' bloquea los scripts inline.
(() => {
  const jsx = (type, props, key) => React.createElement(type, key === undefined ? props : {...props, key});
  window.jsxRuntime = {Fragment: React.Fragment, jsx, jsxs: jsx};
})();
