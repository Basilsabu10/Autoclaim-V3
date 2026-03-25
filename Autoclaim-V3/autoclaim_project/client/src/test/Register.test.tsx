/**
 * Unit tests for the Register component.
 *
 * TC-49: Register form renders all fields
 * TC-   : All required fields are present
 * TC-   : Optional fields (Policy ID, Vehicle Number) not required
 * TC-   : Password field enforces minLength=6 via HTML attribute
 * TC-   : Calls axios.post on form submit
 * TC-   : Shows alert and navigates to / on success
 * TC-   : Shows alert on registration failure (duplicate email etc.)
 * TC-   : Button shows loading state while submitting
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import axios from 'axios';
import Register from '../components/Register';

vi.mock('axios');
const mockedAxios = axios as typeof axios & { post: ReturnType<typeof vi.fn> };

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

let alertMock: ReturnType<typeof vi.fn>;

function renderRegister() {
  return render(
    <MemoryRouter>
      <Register />
    </MemoryRouter>
  );
}

describe('Register Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    alertMock = vi.spyOn(window, 'alert').mockImplementation(() => {});
  });

  afterEach(() => {
    alertMock.mockRestore();
  });

  // ── Rendering ──────────────────────────────────────────────────────────

  it('TC-49: renders heading "Join AUTOCLAIM"', () => {
    renderRegister();
    expect(screen.getByText(/join autoclaim/i)).toBeInTheDocument();
  });

  it('TC-49: renders Full Name input', () => {
    renderRegister();
    expect(screen.getByPlaceholderText(/full name/i)).toBeInTheDocument();
  });

  it('TC-49: renders Email input', () => {
    renderRegister();
    expect(screen.getByPlaceholderText(/email address/i)).toBeInTheDocument();
  });

  it('TC-49: renders Policy ID input (optional)', () => {
    renderRegister();
    expect(screen.getByPlaceholderText(/policy id/i)).toBeInTheDocument();
  });

  it('TC-49: renders Vehicle Number input (optional)', () => {
    renderRegister();
    expect(screen.getByPlaceholderText(/vehicle number/i)).toBeInTheDocument();
  });

  it('TC-49: renders Password input', () => {
    renderRegister();
    expect(screen.getByPlaceholderText(/create a password/i)).toBeInTheDocument();
  });

  it('TC-49: renders Create Account button', () => {
    renderRegister();
    expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
  });

  it('renders Sign In link to navigate back to login', () => {
    renderRegister();
    expect(screen.getByRole('link', { name: /sign in/i })).toBeInTheDocument();
  });

  // ── Input Constraints ─────────────────────────────────────────────────

  it('password input has minLength=6 attribute', () => {
    renderRegister();
    const passInput = screen.getByPlaceholderText(/create a password/i) as HTMLInputElement;
    expect(passInput.minLength).toBe(6);
  });

  it('name, email, and password inputs are required', () => {
    renderRegister();
    expect((screen.getByPlaceholderText(/full name/i) as HTMLInputElement).required).toBe(true);
    expect((screen.getByPlaceholderText(/email address/i) as HTMLInputElement).required).toBe(true);
    expect((screen.getByPlaceholderText(/create a password/i) as HTMLInputElement).required).toBe(true);
  });

  it('policy ID and vehicle number are NOT required', () => {
    renderRegister();
    expect((screen.getByPlaceholderText(/policy id/i) as HTMLInputElement).required).toBe(false);
    expect((screen.getByPlaceholderText(/vehicle number/i) as HTMLInputElement).required).toBe(false);
  });

  // ── Input Interaction ─────────────────────────────────────────────────

  it('captures all field values', async () => {
    renderRegister();
    await userEvent.type(screen.getByPlaceholderText(/full name/i), 'John Doe');
    await userEvent.type(screen.getByPlaceholderText(/email address/i), 'john@test.com');
    await userEvent.type(screen.getByPlaceholderText(/policy id/i), 'POL001');
    await userEvent.type(screen.getByPlaceholderText(/vehicle number/i), 'KL01AB1234');
    await userEvent.type(screen.getByPlaceholderText(/create a password/i), 'secret123');

    expect((screen.getByPlaceholderText(/full name/i) as HTMLInputElement).value).toBe('John Doe');
    expect((screen.getByPlaceholderText(/email address/i) as HTMLInputElement).value).toBe('john@test.com');
    expect((screen.getByPlaceholderText(/policy id/i) as HTMLInputElement).value).toBe('POL001');
    expect((screen.getByPlaceholderText(/vehicle number/i) as HTMLInputElement).value).toBe('KL01AB1234');
    expect((screen.getByPlaceholderText(/create a password/i) as HTMLInputElement).value).toBe('secret123');
  });

  // ── Registration Success ──────────────────────────────────────────────

  it('calls axios.post on form submit', async () => {
    mockedAxios.post = vi.fn().mockResolvedValue({ data: {} });
    renderRegister();
    fireEvent.submit(screen.getByRole('button', { name: /create account/i }).closest('form')!);
    await waitFor(() => expect(mockedAxios.post).toHaveBeenCalled());
  });

  it('shows success alert and navigates to / after registration', async () => {
    mockedAxios.post = vi.fn().mockResolvedValue({ data: {} });
    renderRegister();
    fireEvent.submit(screen.getByRole('button', { name: /create account/i }).closest('form')!);
    await waitFor(() => {
      expect(alertMock).toHaveBeenCalledWith(expect.stringContaining('Successful'));
      expect(mockNavigate).toHaveBeenCalledWith('/');
    });
  });

  // ── Loading State ─────────────────────────────────────────────────────

  it('shows "Creating account..." while request is pending', async () => {
    mockedAxios.post = vi.fn().mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 500))
    );
    renderRegister();
    fireEvent.submit(screen.getByRole('button', { name: /create account/i }).closest('form')!);
    expect(await screen.findByText(/creating account/i)).toBeInTheDocument();
  });

  it('button is disabled while loading', async () => {
    mockedAxios.post = vi.fn().mockImplementation(
      () => new Promise((resolve) => setTimeout(resolve, 500))
    );
    renderRegister();
    const button = screen.getByRole('button', { name: /create account/i });
    fireEvent.submit(button.closest('form')!);
    await screen.findByText(/creating account/i);
    expect(button).toBeDisabled();
  });

  // ── Registration Failure ──────────────────────────────────────────────

  it('shows alert on duplicate email failure', async () => {
    mockedAxios.post = vi.fn().mockRejectedValue({
      response: { data: { detail: 'Email already registered' } },
    });
    renderRegister();
    fireEvent.submit(screen.getByRole('button', { name: /create account/i }).closest('form')!);
    await waitFor(() => {
      expect(alertMock).toHaveBeenCalledWith(expect.stringContaining('already registered'));
    });
  });

  it('does not navigate on failure', async () => {
    mockedAxios.post = vi.fn().mockRejectedValue({ message: 'Network Error' });
    renderRegister();
    fireEvent.submit(screen.getByRole('button', { name: /create account/i }).closest('form')!);
    await waitFor(() => expect(alertMock).toHaveBeenCalled());
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
