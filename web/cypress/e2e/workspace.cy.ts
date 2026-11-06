/**
 * @file workspace.cy.ts
 * @brief Tests of preparing, saving and undoing a study
 * @author Lukas (Viridis) Dubsik
 * @date 6-11-2026
 * @version 0.1
 */

/**
 * AI DISCLAIMER
 *
 * These tests were generated using AI to test the
 * application funcionalitya and refined afterwards
 * to suit the requested needs of testing.
 */

import { addTarget, createStudy, readWorkspace, saveStudy } from "../helpers";

describe("Preparing and saving a study", () => {
  it("rejects an invalid interval and accepts its correction", () => {
    createStudy("Interval correction");
    cy.contains("button", "+ Add target").click();
    cy.get("#target-label").clear().type("Corrected interval");
    cy.get("#target-start").clear().type("200");
    cy.get("#target-end").clear().type("100");
    cy.contains("button", /^Apply target$/).should("be.disabled");
    cy.contains("button", "Start has to be smaller than end").click();
    cy.get("#target-end").should("have.focus");
    readWorkspace().then((workspace) => {
      expect(workspace.study.revisions.at(-1)?.targets).to.have.length(0);
    });
    cy.get("#target-end").clear().type("250");
    cy.contains("button", /^Apply target$/).click();
    cy.contains(".target-row", "Corrected interval").should("be.visible");
    readWorkspace().then((workspace) => {
      expect(workspace.study.revisions.at(-1)?.targets[0]).to.include({
        start: 200,
        end: 250,
      });
    });
  });

  it("reopens saved input without applying an invalid editor draft", () => {
    createStudy("Saved draft recovery");
    addTarget();
    cy.get("#target-end").clear();
    saveStudy();
    readWorkspace().then(({ study }) => {
      cy.contains("button", /^Close working copy$/).click();
      cy.get("#saved-study").select(study.study_id);
      cy.contains("button", /^Open saved study$/).click();
    });
    cy.get("#target-end").should("have.value", "");
    readWorkspace().then((workspace) => {
      expect(workspace.study.revisions.at(-1)?.targets[0].end).to.equal(200);
      expect(workspace.study.draft_buffers.target?.end).to.equal("");
    });
  });

  it("undoes one accepted edit and clears Undo after Save", () => {
    createStudy("Undo interval edit");
    addTarget();
    saveStudy();
    cy.get("#target-end").clear().type("250");
    cy.contains("button", /^Apply target$/).click();
    cy.contains(".target-row", "100–250").should("be.visible");
    cy.contains("button", /^Undo$/).click();
    // Undo restores the accepted interval and keeps the pre-Apply draft.
    cy.get("#target-end").should("have.value", "250");
    readWorkspace().then((workspace) => {
      expect(workspace.study.revisions.at(-1)?.targets[0].end).to.equal(200);
      expect(workspace.study.draft_buffers.target?.end).to.equal("250");
    });
    cy.contains("button", /^Discard edits$/).click();
    cy.get("#target-end").should("have.value", "200");
    saveStudy();
    cy.contains("button", /^Undo$/).should("be.disabled");
  });

  it("retains the study when a malformed request file is refused", () => {
    createStudy("Malformed import");
    addTarget();
    cy.get('[aria-label="Import request file"]').selectFile(
      {
        contents: Cypress.Buffer.from('{"kind":'),
        fileName: "broken.request.json",
        mimeType: "application/json",
      },
      { force: true },
    );
    cy.get('[role="alert"]').should("contain.text", "MALFORMED_JSON");
    cy.get(".context-strip").should("contain.text", "1 accepted targets");
    cy.get("#target-end").should("have.value", "200");
    readWorkspace().then((workspace) => {
      expect(workspace.study.revisions.at(-1)?.targets[0].end).to.equal(200);
    });
  });
});
