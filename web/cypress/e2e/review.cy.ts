/**
 * @file review.cy.ts
 * @brief Tests of evidence import, review decisions and review export
 * @author Lukas (Viridis) Dubsik
 * @version 0.1
 */

/**
 * AI DISCLAIMER
 *
 * These tests were generated using AI to test the
 * application funcionalitya and refined afterwards
 * to suit the requested needs of testing.
 */

import type { ExportPreview } from "../../src/shared/types";
import {
  attachEvidence,
  importStudy,
  inspectEvidence,
  readWorkspace,
  saveStudy,
  type ReviewFile,
} from "../helpers";

describe("Reviewing evidence and exporting decisions", () => {
  it("blocks mismatching evidence and recognises a duplicate", () => {
    importStudy().then(({ evidence }) => {
      cy.contains("nav button", "Review").click();
      inspectEvidence({ ...evidence, request_id: crypto.randomUUID() });
      cy.get(".import-preview").should("contain.text", "CONTEXT_MISMATCH");
      cy.contains("button", /^Attach evidence$/).should("be.disabled");
      readWorkspace().its("study.evidence").should("have.length", 0);
      cy.contains("button", /^Cancel import$/).click();
      attachEvidence(evidence);
      cy.get(".metric-value").should("have.text", "0");
      cy.get(".metric-missing").should("have.text", "not supplied");
      inspectEvidence(evidence);
      cy.contains("button", /^Acknowledge duplicate$/).click();
      readWorkspace().its("study.evidence").should("have.length", 1);
    });
  });

  it("keeps separate collection decisions and retains historical evidence", () => {
    importStudy().then(({ request, evidence }) => {
      attachEvidence(evidence);
      cy.contains("button", /^Add to collection$/).click();
      cy.get("#disposition").select("include_for_review");
      cy.get("#rationale").type("Keep for a separate scientific review.");
      cy.contains("button", /^Apply decision$/).click();
      cy.contains("summary", "Manage collections").click();
      cy.get("#collection-name").type("Alternative selection");
      cy.contains("button", /^Create collection$/).click();
      cy.get("#collection-select").select("Alternative selection");
      cy.contains("button", /^Add to collection$/).click();
      cy.get("#disposition").should("have.value", "undecided");
      cy.contains("button", /^Remove from collection$/).click();
      cy.contains("button", /^Add to collection$/).should("be.visible");
      cy.contains("button", /^Undo$/).click();
      cy.get("#disposition").should("have.value", "undecided");
      cy.get("#collection-select").select("Review collection");
      cy.get("#disposition").should("have.value", "include_for_review");
      cy.get("#rationale").should(
        "have.value",
        "Keep for a separate scientific review.",
      );
      cy.contains("nav button", "Prepare").click();
      cy.contains("button", "Demo target A").click();
      cy.get("#target-end").clear().type("240");
      cy.contains("button", /^Apply target$/).click();
      cy.contains("nav button", "Review").click();
      cy.contains("h2", "No evidence attached to this revision").should(
        "be.visible",
      );
      inspectEvidence(evidence);
      cy.contains("button", /^Attach evidence$/).should("be.disabled");
      cy.contains("button", /^Cancel import$/).click();
      cy.get('[aria-label="Request revision"]').select(
        request.revision.revision_id,
      );
      cy.get(".context-strip").should(
        "contain.text",
        "Historical request context",
      );
      cy.get("#rationale").should(
        "have.value",
        "Keep for a separate scientific review.",
      );
    });
  });

  it("downloads a draft review with the original evidence bytes and checksum", () => {
    importStudy().then(({ evidence }) => {
      attachEvidence(evidence);
      cy.contains("button", /^Add to collection$/).click();
      cy.get("#disposition").select("needs_clarification");
      cy.get("#rationale").type("The second metric was not supplied.");
      cy.contains("button", /^Apply decision$/).click();
      saveStudy();
      cy.contains("nav button", "Export").click();
      cy.contains("label", "Review / evidence package").click();
      cy.contains("label", "Review collection")
        .find('input[type="checkbox"]')
        .check();
      cy.intercept("POST", "/api/v1/exports").as("export");
      cy.contains("button", /^Preview saved export$/).click();
      cy.wait<unknown, ExportPreview>("@export").then(({ response }) => {
        expect(response?.statusCode).to.equal(201);
        const preview = response!.body;
        cy.contains("h2", /^Draft review$/).should("be.visible");
        cy.contains("a", "Download draft review").click();
        cy.readFile(
          `${Cypress.config("downloadsFolder")}/${preview.filename}`,
          null,
        ).then((bytes: Buffer) => {
          const text = bytes.toString("utf8");
          const file = JSON.parse(text) as ReviewFile;
          expect(file.review_status).to.equal("draft");
          expect(file.collections[0].memberships[0].rationale).to.equal(
            "The second metric was not supplied.",
          );
          const original = Cypress.Buffer.from(
            file.evidence_files[0].content_base64,
            "base64",
          ).toString("utf8");
          expect(original).to.equal(JSON.stringify(evidence));
          cy.task("sha256", original).should(
            "equal",
            file.evidence_files[0].sha256,
          );
          cy.task("sha256", text).should("equal", preview.sha256);
        });
      });
    });
  });
});
