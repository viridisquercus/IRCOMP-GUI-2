/*************************************************************************
 * Name: Lukas (Viridis) Dubsik
 *************************************************************************/
import { createHash } from "node:crypto";
import { defineConfig } from "cypress";

export default defineConfig({
  video: false,
  allowCypressEnv: false,
  retries: 0,
  viewportWidth: 1440,
  viewportHeight: 1000,
  e2e: {
    baseUrl: "http://127.0.0.1:8765",
    specPattern: "cypress/e2e/**/*.cy.ts",
    supportFile: false,
    fixturesFolder: "../contracts/examples",
    setupNodeEvents(on) {
      on("task", {
        sha256(text: string) {
          return createHash("sha256").update(text).digest("hex");
        },
      });
    },
  },
});
