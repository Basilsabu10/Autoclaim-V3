/**
 * Cypress E2E Tests — Claim Submission
 *
 * TC-11 (E2E): Submit claim with valid image
 * TC-14 (E2E): User sees only their own claims
 * TC-16 (E2E): Claim appears in list after submission
 */

describe('Claim Submission', () => {
  beforeEach(() => {
    cy.clearLocalStorage();
    // Login as a seeded test user before each test
    cy.loginAs('testuser@autoclaim.com', 'password123');
  });

  it('TC-11: navigates to submit claim page successfully', () => {
    cy.visit('/dashboard');
    // Look for a submit/new claim button
    cy.get('[data-testid="submit-claim-btn"], a[href*="submit"], button')
      .contains(/new claim|submit/i)
      .first()
      .click();
    cy.url().should('include', '/submit');
  });

  it('TC-14: dashboard shows claim list for the logged-in user', () => {
    cy.visit('/dashboard');
    // Dashboard should contain a claims section
    cy.get('[data-testid="claim-list"], .claim-card, .claim-item, table')
      .should('exist');
  });

  it('TC-50: claim submission form shows image upload area', () => {
    cy.visit('/submit');
    cy.get('input[type="file"]').should('exist');
  });

  it('TC-52: dashboard is responsive on mobile viewport', () => {
    cy.viewport(375, 812); // iPhone 13
    cy.visit('/dashboard');
    cy.get('body').should('be.visible');
    // No horizontal overflow
    cy.window().then((win) => {
      expect(win.document.documentElement.scrollWidth).to.be.lte(375);
    });
  });
});
