/**
 * Unit tests for the ProtectedRoute component.
 *
 * TC-07 (frontend): Accessing protected page without token redirects to /
 * TC-   : User with correct role sees children
 * TC-   : Admin user redirected to /admin when accessing user-only route
 * TC-   : Agent user redirected to /agent when accessing wrong role route
 */

import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { describe, it, expect, beforeEach } from 'vitest';
import ProtectedRoute from '../components/ProtectedRoute';

function renderWithRouter(
  children: React.ReactNode,
  initialEntries: string[] = ['/protected'],
  requiredRole?: string
) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/" element={<div>Login Page</div>} />
        <Route path="/dashboard" element={<div>Dashboard</div>} />
        <Route path="/admin" element={<div>Admin Page</div>} />
        <Route path="/agent" element={<div>Agent Page</div>} />
        <Route
          path="/protected"
          element={
            <ProtectedRoute requiredRole={requiredRole}>
              {children}
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>
  );
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('TC-07: redirects to / when no token is stored', () => {
    renderWithRouter(<div>Secret Content</div>);
    expect(screen.getByText(/login page/i)).toBeInTheDocument();
    expect(screen.queryByText(/secret content/i)).not.toBeInTheDocument();
  });

  it('renders children when token exists and no role required', () => {
    localStorage.setItem('token', 'valid_token');
    localStorage.setItem('role', 'user');
    renderWithRouter(<div>Secret Content</div>);
    expect(screen.getByText(/secret content/i)).toBeInTheDocument();
  });

  it('renders children when token and role both match', () => {
    localStorage.setItem('token', 'valid_token');
    localStorage.setItem('role', 'admin');
    renderWithRouter(<div>Admin Only Content</div>, ['/protected'], 'admin');
    expect(screen.getByText(/admin only content/i)).toBeInTheDocument();
  });

  it('redirects admin to /admin when accessing user-only route', () => {
    localStorage.setItem('token', 'valid_token');
    localStorage.setItem('role', 'admin');
    renderWithRouter(<div>User Content</div>, ['/protected'], 'user');
    expect(screen.getByText(/admin page/i)).toBeInTheDocument();
    expect(screen.queryByText(/user content/i)).not.toBeInTheDocument();
  });

  it('redirects agent to /agent when accessing user-only route', () => {
    localStorage.setItem('token', 'valid_token');
    localStorage.setItem('role', 'agent');
    renderWithRouter(<div>User Content</div>, ['/protected'], 'user');
    expect(screen.getByText(/agent page/i)).toBeInTheDocument();
    expect(screen.queryByText(/user content/i)).not.toBeInTheDocument();
  });

  it('redirects regular user to /dashboard when accessing wrong role route', () => {
    localStorage.setItem('token', 'valid_token');
    localStorage.setItem('role', 'user');
    renderWithRouter(<div>Admin Content</div>, ['/protected'], 'admin');
    expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
    expect(screen.queryByText(/admin content/i)).not.toBeInTheDocument();
  });
});
