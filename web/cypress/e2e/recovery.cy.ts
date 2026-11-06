/**
 * @file recovery.cy.ts
 * @brief Tests of recovery from failed requests and stable exports
 * @author Lukas (Viridis) Dubsik
 * @date 6-11-2026
 * @version 0.1
 */
import type { ExportPreview, Revision } from "../../src/shared/types";
import { addTarget, createStudy, readWorkspace, saveStudy } from "../helpers";

describe("Recovering from failed requests and keeping saved exports stable", () => {
  it("retains an edit after a failed Save and allows a real retry", () => {
    createStudy("Save retry");
    addTarget();
    cy.intercept(
      { method: "POST", url: "**/save", times: 1 },
      {
        statusCode: 503,
        body: {
          error: {
            code: "PERSISTENCE_UNAVAILABLE",
            message: "Storage is temporarily unavailable.",
            diagnostics: [],
          },
        },
      },
    ).as("failedSave");
    cy.contains("button", /^Save study$/).click();
    cy.wait("@failedSave");
    cy.get(".save-status").should("have.text", "Save failed");
    cy.get('[role="alert"]').should(
      "contain.text",
      "Storage is temporarily unavailable",
    );
    cy.get("#target-end").should("have.value", "200");
    readWorkspace().then((workspace) => {
      expect(workspace.base_saved_version).to.equal(0);
      expect(workspace.study.revisions.at(-1)?.targets[0].end).to.equal(200);
    });
    saveStudy();
    readWorkspace().its("base_saved_version").should("equal", 1);
  });

  it("keeps newer typing when an earlier Save response arrives", () => {
    createStudy("Delayed Save");
    addTarget();
    cy.intercept("POST", "**/save", (request) => {
      request.continue((response) => {
        response.setDelay(1000);
      });
    }).as("delayedSave");
    cy.contains("button", /^Save study$/).click();
    cy.get("#target-end").clear().type("250");
    cy.wait("@delayedSave");
    cy.get("#target-end").should("have.value", "250");
    cy.get(".save-status").should("contain.text", "Unsaved");
    readWorkspace().then((workspace) => {
      expect(workspace.base_saved_version).to.equal(1);
      expect(workspace.study.revisions.at(-1)?.targets[0].end).to.equal(200);
      expect(workspace.study.draft_buffers.target).to.equal(null);
    });
  });

  it("refreshes accepted state after a command response is lost", () => {
    createStudy("Lost command response");
    cy.contains("button", "+ Add target").click();
    cy.get("#target-label").clear().type("Accepted once");
    cy.get("#target-start").clear().type("100");
    cy.get("#target-end").clear().type("200");
    // Let the real fetch finish, then reject before the controller reads it.
    cy.window().then((window) => {
      const originalFetch = window.fetch.bind(window);
      let dropResponse = true;
      cy.stub(window, "fetch").callsFake(
        async (input: RequestInfo | URL, init?: RequestInit) => {
          const response = await originalFetch(input, init);
          if (dropResponse && String(input).endsWith("/commands")) {
            dropResponse = false;
            throw new TypeError("The command response was lost.");
          }
          return response;
        },
      );
    });
    cy.contains("button", /^Apply target$/).click();
    cy.get('[role="alert"]').should(
      "contain.text",
      "local service is unavailable",
    );
    cy.contains("button", /^Refresh working state$/).click();
    cy.get(".context-strip").should("contain.text", "1 accepted targets");
    readWorkspace().then((workspace) => {
      expect(workspace.study.revisions.at(-1)?.targets).to.have.length(1);
      expect(workspace.study.revisions.at(-1)?.targets[0].end).to.equal(200);
    });
  });

  it("exports the saved interval while a newer accepted edit is unsaved", () => {
    createStudy("Saved export");
    addTarget();
    saveStudy();
    cy.get("#target-end").clear().type("250");
    cy.contains("button", /^Apply target$/).click();
    cy.contains("nav button", "Export").click();
    cy.contains("button", /^Preview saved export$/).should("be.disabled");
    cy.intercept("POST", "/api/v1/exports").as("export");
    cy.contains("button", /^Export last saved$/).click();
    cy.wait<unknown, ExportPreview>("@export").then(({ response }) => {
      const preview = response!.body;
      cy.contains("a", "Download snapshot").click();
      cy.readFile(
        `${Cypress.config("downloadsFolder")}/${preview.filename}`,
      ).then((file: { revision: Revision }) => {
        expect(file.revision.targets[0].end).to.equal(200);
      });
      readWorkspace().then((workspace) => {
        expect(workspace.study.revisions.at(-1)?.targets[0].end).to.equal(250);
      });
    });
  });
});
