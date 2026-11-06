/**
 * @file test.mjs
 * @brief Start the service on a free port and run Cypress against it
 * @author Lukas (Viridis) Dubsik
 * @version 0.1
 *
 * Detailed description:
 *  Every run gets its own temporary database, so the tests never
 *  touch the real saved studies.
 *  Use --open for the interactive Cypress window.
 */
import { spawn } from "node:child_process";
import { once } from "node:events";
import {
  closeSync,
  mkdtempSync,
  openSync,
  readFileSync,
  rmSync,
} from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import cypress from "cypress";

async function main() {
  const root = fileURLToPath(new URL("../../", import.meta.url));
  const directory = mkdtempSync(join(tmpdir(), "ircomp-cypress-"));
  const logPath = join(directory, "server.log");
  const log = openSync(logPath, "w");

  // Ask the OS for an available port instead of reusing a running application.
  const listener = createServer();
  listener.listen(0, "127.0.0.1");
  await once(listener, "listening");
  const address = listener.address();
  if (!address || typeof address === "string") {
    throw new Error("Could not select a local test port.");
  }
  const port = address.port;
  await new Promise((resolve, reject) => {
    listener.close((error) => (error ? reject(error) : resolve(undefined)));
  });

  const server = spawn(
    join(root, ".venv/bin/python"),
    ["-m", "ircomp_gui", "--port", String(port)],
    {
      cwd: root,
      env: {
        ...process.env,
        IRCOMP_GUI_DATABASE: join(directory, "workspace.sqlite3"),
        IRCOMP_GUI_WEB: join(root, "web/dist"),
      },
      stdio: ["ignore", log, log],
    },
  );
  let startError;
  server.on("error", (error) => {
    startError = error;
  });
  const stop = () => {
    server.kill("SIGTERM");
  };
  process.once("SIGINT", stop);
  process.once("SIGTERM", stop);

  try {
    const baseUrl = `http://127.0.0.1:${port}`;
    let ready = false;
    for (let attempt = 0; attempt < 75; attempt += 1) {
      if (startError) throw startError;
      if (server.exitCode !== null) {
        throw new Error("The test server stopped before it was ready.");
      }
      try {
        const response = await fetch(`${baseUrl}/api/v1/catalogue`, {
          signal: AbortSignal.timeout(500),
        });
        if (response.ok) {
          ready = true;
          break;
        }
      } catch {
        // Uvicorn has not opened its listening socket yet.
      }
      await setTimeout(200);
    }
    if (!ready)
      throw new Error("The test server did not start within 15 seconds.");

    const options = {
      project: join(root, "web"),
      config: { e2e: { baseUrl } },
    };
    if (process.argv.includes("--open")) {
      await cypress.open(options);
    } else {
      const results = await cypress.run({ ...options, browser: "electron" });
      if ("failures" in results || results.totalFailed > 0) {
        process.exitCode = 1;
      }
    }
  } catch (error) {
    console.error(error);
    console.error(readFileSync(logPath, "utf8"));
    process.exitCode = 1;
  } finally {
    process.removeListener("SIGINT", stop);
    process.removeListener("SIGTERM", stop);
    if (server.exitCode === null && !startError) {
      const stopped = once(server, "exit");
      server.kill("SIGTERM");
      const timeout = globalThis.setTimeout(() => server.kill("SIGKILL"), 5000);
      await stopped;
      clearTimeout(timeout);
    }
    closeSync(log);
    rmSync(directory, { recursive: true, force: true });
  }
}

await main();
