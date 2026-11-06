/*************************************************************************
 * Name: Lukas (Viridis) Dubsik
 *************************************************************************/
import type {
  Bundle,
  Collection,
  Revision,
  Workspace,
} from "../src/shared/types";

type RequestFile = {
  study_id: string;
  request_id: string;
  title: string;
  revision: Revision;
  target_labels: Record<string, string>;
};

export type ReviewFile = {
  review_status: "draft" | "reviewed";
  collections: Collection[];
  evidence_files: { content_base64: string; sha256: string }[];
};

export function createStudy(title: string) {
  cy.visit("/");
  cy.contains("summary", "New / Open / Rename / Duplicate").click();
  cy.get("#new-study-title").type(title);
  cy.contains("button", /^Create study$/).click();
  cy.contains("h1", "Prepare the request").should("be.visible");
}

export function addTarget(label = "Test interval", start = "100", end = "200") {
  cy.contains("button", "+ Add target").click();
  cy.get("#target-label").clear().type(label);
  cy.get("#target-start").clear().type(start);
  cy.get("#target-end").clear().type(end);
  cy.contains("button", /^Apply target$/).click();
  cy.get(".context-strip").should("contain.text", "1 accepted targets");
}

export function saveStudy() {
  cy.contains("button", /^Save study$/).click();
  cy.get(".save-status").should("contain.text", "Saved");
}

export function readWorkspace() {
  return cy.window().then((window) => {
    const id = window.sessionStorage.getItem("ircomp.workspace");
    expect(id).to.be.a("string").and.not.be.empty;
    return cy.request<Workspace>(`/api/v1/workspaces/${id}`).its("body");
  });
}

export function importStudy() {
  // Give every scenario a separate lineage, even when a previous one saved it.
  return cy.fixture<RequestFile>("request-valid.json").then((request) => {
    request.study_id = crypto.randomUUID();
    request.request_id = crypto.randomUUID();
    request.revision.revision_id = crypto.randomUUID();
    cy.visit("/");
    cy.contains("summary", "New / Open / Rename / Duplicate").click();
    cy.get('[aria-label="Import request file"]').selectFile(
      {
        contents: Cypress.Buffer.from(JSON.stringify(request)),
        fileName: "test.request.json",
        mimeType: "application/json",
      },
      { force: true },
    );
    cy.contains("button", /^Open request$/).click();
    cy.contains("h1", "Prepare the request").should("be.visible");
    return cy.fixture<Bundle>("evidence-valid.json").then((evidence) => {
      evidence.bundle_id = crypto.randomUUID();
      evidence.request_id = request.request_id;
      evidence.context = request.revision;
      return { request, evidence };
    });
  });
}

export function inspectEvidence(evidence: Bundle) {
  cy.get('[aria-label="Import evidence file"]').selectFile(
    {
      contents: Cypress.Buffer.from(JSON.stringify(evidence)),
      fileName: "test.evidence.json",
      mimeType: "application/json",
    },
    { force: true },
  );
  cy.get('[aria-label="Import preview"]').should("be.visible");
}

export function attachEvidence(evidence: Bundle) {
  cy.contains("nav button", "Review").click();
  inspectEvidence(evidence);
  cy.contains("button", /^Attach evidence$/).click();
  cy.contains("h2", "Synthetic candidate A").should("be.visible");
}
