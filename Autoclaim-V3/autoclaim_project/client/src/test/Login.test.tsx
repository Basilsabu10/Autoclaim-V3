/**
 * Unit tests for the Login component.
 *
 * TC-48: Login form renders with email + password fields
 * TC-   : Inputs are controlled (typing updates values)
 * TC-   : Submit button shows loading state
 * TC-   : Calls axios.post on form submit
 * TC-   : Stores token in localStorage on success
 * TC-   : Navigates to /dashboard for 'user' role
 * TC-   : Navigates to /admin for 'admin' role
 * TC-   : Navigates to /agent for 'agent' role
 * TC-   : Shows alert on login failure
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import axios from 'axios';
import Login from '../components/Login';

// Mock axios
vi.mock('axios');
const mockedAxios = axios as typeof axios & { post: ReturnType<typeof vi.fn> };

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

// Mock window.alert
let alertMock: ReturnType<typeof vi.fn>;

function renderLogin() {
  return render(
    <MemoryRouter>
      <Login />
    </MemoryRouter>
  );
}

describe('Login Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    alertMock = vi.spyOn(window, 'alert').mockImplementation(() => {});
    localStorage.clear();
  });

  afterEach(() => {
    alertMock.mockRestore();
  });

  // ── Rendering ──────────────────────────────────────────────────────────

  it('TC-48: renders email and password inputs', () => {
    renderLogin();
    expect(screen.getByPlaceholderText(/email address/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/password/i)).toBeInTheDocument();
  });

  it('TC-48: renders Sign In button', () => {
    renderLogin();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('renders welcome heading', () => {
    renderLogin();
    expect(screen.getByText(/welcome to autoclaim/i)).toBeInTheDocument();
  });

  it('renders link to register page', () => {
    renderLogin();
    expect(screen.getByRole('link', { name: /create one/i })).toBeInTheDocument();
  });

  // ── Input Interaction ─────────────────────────────────────────────────

  it('captures email input correctly', async () => {
    renderLogin();
    const emailInput = screen.getByPlaceholderText(/email address/i) as HTMLInputElement;
    await userEvent.type(emailInput, 'test@example.com');
    expect(emailInput.value).toBe('test@example.com');
  });

  it('captures password input correctly', async () => {
    renderLogin();
    const passInput = screen.getByPlaceholderText(/password/i) as HTMLInputElement;
    await userEvent.type(passInput, 'mypassword');
    expect(passInput.value).toBe('mypassword');
  });

  // ── Login Success ─────────────────────────────────────────────────────

  it('navigates to /dashboard for role=user', async () => {
    mockedAxios.post = vi.fn().mockResolvedValue({
      data: { access_token: 'tok_user', role: 'user' },
    });
    renderLogin();
    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }).closest('form')!);
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/dashboard'));
  });

  it('navigates to /admin for role=admin', async () => {
    mockedAxios.post = vi.fn().mockResolvedValue({
      data: { access_token: 'tok_admin', role: 'admin' },
    });
    renderLogin();
    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }).closest('form')!);
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/admin'));
  });

  it('navigates to /agent for role=agent', async () => {
    mockedAxios.post = vi.fn().mockResolvedValue({
      data: { access_token: 'tok_agent', role: 'agent' },
    });
    renderLogin();
    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }).closest('form')!);
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/agent'));
  });

  it('stores token and role in localStorage on success', async () => {
    mockedAxios.post = vi.fn().mockResolvedValue({
      data: { access_token: 'mytoken123', role: 'user' },
    });
    renderLogin();
    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }).closest('form')!);
    await waitFor(() => {
      expect(localStorage.getItem('token')).toBe('mytoken123');
      expect(localStorage.getItem('role')).toBe('user');
    });
  });

  // ── Loading State ─────────────────────────────────────────────────────

  it('shows "Signing in..." while request is pending', async () => {
    mockedAxios.post = vi.fn().mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 500))
    );
    renderLogin();
    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }).closest('form')!);
    expect(await screen.findByText(/signing in/i)).toBeInTheDocument();
  });

  // ── Login Failure ─────────────────────────────────────────────────────

  it('shows alert on login failure', async () => {
    mockedAxios.post = vi.fn().mockRejectedValue({
      response: { data: { detail: 'Invalid credentials' } },
    });
    renderLogin();
    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }).closest('form')!);
    await waitFor(() => {
      expect(alertMock).toHaveBeenCalledWith(
        expect.stringContaining('Invalid credentials')
      );
    });
  });

  it('does not navigate on failure', async () => {
    mockedAxios.post = vi.fn().mockRejectedValue({ message: 'Network Error' });
    renderLogin();
    fireEvent.submit(screen.getByRole('button', { name: /sign in/i }).closest('form')!);
    await waitFor(() => expect(alertMock).toHaveBeenCalled());
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
