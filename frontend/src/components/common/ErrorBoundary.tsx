import React from "react";

interface Props {
  children: React.ReactNode;
}

interface State {
  error: Error | null;
}

/** Global error boundary: a render crash shows a recoverable panel instead of a blank page. */
export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("Unhandled render error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-background p-8">
          <div className="max-w-lg space-y-4 rounded-lg border border-destructive/40 bg-card p-6 text-card-foreground">
            <h1 className="text-lg font-semibold">Something went wrong</h1>
            <p className="text-sm text-muted-foreground">
              The interface hit an unexpected error. Your device library and saved
              systems are not affected.
            </p>
            <pre className="max-h-40 overflow-auto rounded bg-muted p-3 text-xs">
              {this.state.error.message}
            </pre>
            <div className="flex gap-2">
              <button
                className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground"
                onClick={() => this.setState({ error: null })}
              >
                Try again
              </button>
              <button
                className="rounded-md border px-3 py-1.5 text-sm font-medium"
                onClick={() => window.location.assign("/")}
              >
                Go to home
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
