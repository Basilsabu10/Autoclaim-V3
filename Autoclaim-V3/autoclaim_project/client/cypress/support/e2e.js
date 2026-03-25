// cypress/support/e2e.js
// Global support file — runs before every test file

// Custom command: login programmatically via API (avoids UI login overhead)
Cypress.Commands.add('loginAs', (email, password) => {
  cy.request({
    method: 'POST',
    url: 'http://localhost:8000/login',
    form: true,
    body: { username: email, password: password },
  }).then((resp) => {
    window.localStorage.setItem('token', resp.body.access_token);
    window.localStorage.setItem('role', resp.body.role);
  });
});
