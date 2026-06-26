import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  failed: boolean;
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("React view failed", error, info);
  }

  render() {
    if (this.state.failed) {
      return (
        <section role="alert">
          <h1>Esta vista tuvo un problema</h1>
          <p>La falla quedó contenida. Puedes volver a una ruta segura.</p>
          <a href="/react">Volver al inicio</a>
        </section>
      );
    }
    return this.props.children;
  }
}
