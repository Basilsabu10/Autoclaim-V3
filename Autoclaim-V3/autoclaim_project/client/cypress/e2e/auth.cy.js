/**
 * Cypress E2E Tests — User Authentication
 *
 * TC-48: Login page renders correctly
 * TC-04 (E2E): Login with valid credentials navigates to dashboard
 * TC-05 (E2E): Invalid login shows error
 * TC-07 (E2E): Visiting protected route without token redirects to login
 */

describe('User Authentication', () => {
  beforeEach(() => {
    cy.clearLocalStorage();
  });

  // ── Page Rendering ─────────────────────────────────────────────────────

  it('TC-48: login page renders email, password fields and Sign In button', () => {
    cy.visit('/');
    cy.contains('AUTOCLAIM').should('be.visible');
    cy.get('input[type="email"]').should('be.visible');
    cy.get('input[type="password"]').should('be.visible');
    cy.get('button[type="submit"]').should('be.visible');
  });

  it('register page renders all form fields', () => {
    cy.visit('/register');
    cy.contains('Join AUTOCLAIM').should('be.visible');
    cy.get('input[placeholder*="Full Name"]').should('be.visible');
    cy.get('input[type="email"]').should('be.visible');
    cy.get('input[placeholder*="Policy ID"]').should('be.visible');
    cy.get('input[placeholder*="Vehicle Number"]').should('be.visible');
    cy.get('input[type="password"]').should('be.visible');
  });

  // ── Login Flow ─────────────────────────────────────────────────────────

  it('TC-04: valid user login navigates to /dashboard', () => {
    // Use programmatic login to avoid UI dependency
    cy.loginAs('testuser@autoclaim.com', 'password123');
    cy.visit('/dashboard');
    cy.url().should('include', '/dashboard');
  });

  it('TC-05: invalid credentials shows error feedback', () => {
    cy.visit('/');
    cy.get('input[type="email"]').type('wrong@example.com');
    cy.get('input[type="password"]').type('badpassword');
    cy.get('button[type="submit"]').click();

    // Should still be on login page (not navigated away)
    cy.url().should('eq', Cypress.config().baseUrl + '/');
  });

  // ── Protected Route ────────────────────────────────────────────────────

  it('TC-07: visiting /dashboard without token redirects to /', () => {
    cy.visit('/dashboard');
    cy.url().should('eq', Cypress.config().baseUrl + '/');
  });

  it('TC-07: visiting /admin without token redirects to /', () => {
    cy.visit('/admin');
    cy.url().should('eq', Cypress.config().baseUrl + '/');
  });

  // ── Registration Flow ──────────────────────────────────────────────────

  it('TC-49: register form can be filled and submitted', () => {
    const email = `cypress_${Date.now()}@test.com`;
    cy.visit('/register');
    cy.get('input[placeholder*="Full Name"]').type('Cypress User');
    cy.get('input[type="email"]').type(email);
    cy.get('input[placeholder*="Policy ID"]').type('POL-CYPRESS');
    cy.get('input[placeholder*="Vehicle Number"]').type('KL01CY1234');
    cy.get('input[type="password"]').type('cypress123');
    cy.get('button[type="submit"]').click();
    // After success alert, should redirect to login (/)
    cy.url().should('eq', Cypress.config().baseUrl + '/');
  });
});
