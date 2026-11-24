// Copia a dsia_web/static/vendor los builds UMD fijados en package-lock.json, con sus licencias y un
// manifiesto de sha256. Sin bundler: los ficheros salen tal cual de npm, así que `npm ci` + este script
// reproducen byte a byte lo versionado (el CI lo comprueba con `git diff --exit-code`).
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const modules = join(here, "node_modules");
const out = join(here, "..", "dsia_web", "static", "vendor");

// > Orden de carga en el navegador: React, React DOM, el puente jsx-runtime propio y React Flow.
const FILES = [
  ["react/umd/react.production.min.js", "react.production.min.js"],
  ["react-dom/umd/react-dom.production.min.js", "react-dom.production.min.js"],
  ["@xyflow/react/dist/umd/index.js", "xyflow-react.umd.js"],
  ["@xyflow/react/dist/style.css", "xyflow-react.css"],
];
const LICENSE_NAMES = ["LICENSE", "LICENSE.md", "LICENSE.txt", "license", "license.md"];

const lock = JSON.parse(readFileSync(join(here, "package-lock.json"), "utf8"));
const installed = Object.entries(lock.packages)
  .filter(([path]) => path.startsWith("node_modules/"))
  .map(([path, info]) => ({ name: path.slice("node_modules/".length), version: info.version, license: info.license }))
  // > Los @types solo describen tipos: no llegan a ningún build.
  .filter((pkg) => !pkg.name.startsWith("@types/"))
  .sort((a, b) => a.name.localeCompare(b.name, "en"));

const sha256 = (buffer) => createHash("sha256").update(buffer).digest("hex");

rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });

const files = {};
for (const [source, target] of FILES) {
  const buffer = readFileSync(join(modules, source));
  writeFileSync(join(out, target), buffer);
  const pkg = installed.find((candidate) => source.startsWith(`${candidate.name}/`));
  const path = source.slice(pkg.name.length + 1);
  files[target] = { source: `${pkg.name}@${pkg.version}/${path}`, bytes: buffer.length, sha256: sha256(buffer) };
}

const notices = installed.map((pkg) => {
  const folder = join(modules, pkg.name);
  const name = readdirSync(folder).find((entry) => LICENSE_NAMES.includes(entry));
  if (!name) throw new Error(`Sin fichero de licencia en ${pkg.name}`);
  const text = readFileSync(join(folder, name), "utf8").trim();
  return `${"=".repeat(72)}\n${pkg.name}@${pkg.version} (${pkg.license})\n${"=".repeat(72)}\n\n${text}\n`;
});
const licenses = "Licencias de terceros incluidas en dsia_web/static/vendor (generado por frontend/vendor.mjs).\n"
  + "React y React DOM se sirven como UMD; React Flow empaqueta @xyflow/system, zustand, classcat y d3.\n\n"
  + notices.join("\n");
writeFileSync(join(out, "THIRD_PARTY_LICENSES.txt"), licenses);
files["THIRD_PARTY_LICENSES.txt"] = { source: "frontend/vendor.mjs", bytes: Buffer.byteLength(licenses),
  sha256: sha256(Buffer.from(licenses)) };

const manifest = {
  generated_by: "proyectos/proyecto_iii/frontend/vendor.mjs",
  packages: Object.fromEntries(installed.map((pkg) => [pkg.name, pkg.version])),
  files,
};
writeFileSync(join(out, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`${Object.keys(files).length} ficheros en ${out}`);
