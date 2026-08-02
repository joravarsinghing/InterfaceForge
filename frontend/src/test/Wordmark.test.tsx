import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { Wordmark } from '../components/Wordmark';
import { Header } from '../components/Header';
import { ErrorBoundary } from '../components/ErrorBoundary';

describe('Wordmark Color Correction (S6A.6)', () => {
  it('renders Interface and Forge segments with correct theme classes', () => {
    render(<Wordmark data-testid="test-wordmark" />);

    const wordmark = screen.getByTestId('test-wordmark');
    expect(wordmark).toBeInTheDocument();
    expect(wordmark).toHaveClass('wordmark');

    const interfaceSegment = screen.getByText('INTERFACE');
    const forgeSegment = screen.getByText('FORGE');

    expect(interfaceSegment).toBeInTheDocument();
    expect(interfaceSegment).toHaveClass('wordmark-interface');

    expect(forgeSegment).toBeInTheDocument();
    expect(forgeSegment).toHaveClass('wordmark-forge');
  });

  it('renders Wordmark component consistently inside Header logo link', () => {
    const healthState = {
      data: { service_name: 'InterfaceForge Backend', status: 'ok', environment: 'development', version: '0.1.0' },
      loading: false,
      error: null,
    };

    render(<Header healthState={healthState} onRetryHealth={() => {}} />);

    const logoLink = screen.getByRole('link', { name: /InterfaceForge Home/i });
    expect(logoLink).toBeInTheDocument();

    const interfaceText = logoLink.querySelector('.wordmark-interface');
    const forgeText = logoLink.querySelector('.wordmark-forge');

    expect(interfaceText).toBeInTheDocument();
    expect(interfaceText?.textContent).toBe('INTERFACE');
    expect(forgeText).toBeInTheDocument();
    expect(forgeText?.textContent).toBe('FORGE');
  });

  it('renders Wordmark component consistently inside ErrorBoundary fallback', () => {
    const ProblemChild = () => {
      throw new Error('Test application crash');
    };

    // Suppress expected console.error during error boundary test
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <ProblemChild />
      </ErrorBoundary>
    );

    const interfaceText = screen.getByText('INTERFACE');
    const forgeText = screen.getByText('FORGE');

    expect(interfaceText).toHaveClass('wordmark-interface');
    expect(forgeText).toHaveClass('wordmark-forge');

    consoleErrorSpy.mockRestore();
  });
});
