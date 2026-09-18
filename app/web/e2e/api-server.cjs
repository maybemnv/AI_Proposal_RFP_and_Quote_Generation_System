const {execFileSync, spawn} = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "../../..");
const pythonCandidates = [
  process.env.PYTHON,
  path.join(root, ".venv", "Scripts", "python.exe"),
  path.join(root, ".venv", "bin", "python"),
  "python3",
  "python",
].filter(Boolean);
const python = pythonCandidates.find((candidate) => {
  try {
    execFileSync(candidate, ["--version"], {stdio: "ignore"});
    return true;
  } catch {
    return false;
  }
});
if (!python) {
  throw new Error("Python interpreter not found; create .venv or set the PYTHON environment variable.");
}

fs.mkdirSync(path.join(root, "var", "documents"), {recursive: true});

const env = {
  ...process.env,
  APP_ENV: "local-fixture",
  DATABASE_URL: "sqlite+pysqlite:///var/showcase.db",
  STORAGE_DIR: "var/documents",
};

execFileSync(python, ["-m", "app.cli", "reset"], {cwd: root, env, stdio: "inherit"});
const server = spawn(python, ["-m", "uvicorn", "app.api.main:app", "--port", "8106"], {
  cwd: root,
  env,
  stdio: "inherit",
});

const stop = () => {
  server.kill();
  process.exit(0);
};
process.once("SIGINT", stop);
process.once("SIGTERM", stop);
server.once("exit", (code) => process.exit(code ?? 0));
