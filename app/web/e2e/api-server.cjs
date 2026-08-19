const {execFileSync, spawn} = require("node:child_process");
const path = require("node:path");

const root = path.resolve(__dirname, "../../..");
const python = path.join(root, ".venv", "Scripts", "python.exe");
const env = {
  ...process.env,
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
