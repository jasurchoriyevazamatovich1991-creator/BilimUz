import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

/**
 * ONE app-wide boundary (approved decision — not per-layout), wraps
 * <AppRoutes/> in App.tsx. Catches render-time crashes anywhere in the
 * tree and shows a real fallback instead of a blank white screen — the
 * gap identified in the Sprint 14 architecture doc (nothing like this
 * existed anywhere in Sprint 13).
 *
 * Must be a class component — React has no hook-based equivalent for
 * catching render errors (getDerivedStateFromError/componentDidCatch
 * have no Hooks API as of React 19).
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // No system_logs wiring here — that's a backend module reached over
    // HTTP, out of this sprint's scope (would need a new api/systemLogs.ts
    // + a decision about whether client-side crashes should even be sent
    // there, not assumed). console.error is the honest, current behavior.
    console.error("ErrorBoundary caught a render error:", error, errorInfo);
  }

  handleReload = () => {
    this.setState({ hasError: false });
    window.location.href = "/";
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
          <h1 className="text-xl font-semibold text-foreground">Nimadir xato ketdi</h1>
          <p className="mt-2 text-sm text-foreground/60">Sahifani qayta yuklashga urinib ko'ring.</p>
          <button
            type="button"
            onClick={this.handleReload}
            className="mt-6 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            Bosh sahifaga qaytish
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
