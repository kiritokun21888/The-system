import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** When true, render nothing on error (for non-essential effects). */
  silent?: boolean;
  label?: string;
}
interface State {
  hasError: boolean;
  message: string;
}

/**
 * Catches render errors so one broken component (e.g. a WebGL canvas that the
 * GPU/driver rejects) can never blank the whole app. Essential boundaries show
 * a small fallback; `silent` boundaries (background effects) render nothing.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: "" };

  static getDerivedStateFromError(err: unknown): State {
    return { hasError: true, message: err instanceof Error ? err.message : String(err) };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Log for debugging; never rethrow.
    console.error(`[${this.props.label ?? "ErrorBoundary"}]`, error, info.componentStack);
  }

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;
    if (this.props.silent) return null;
    return (
      <div className="glass m-4 flex flex-col items-center justify-center gap-2 p-8 text-center">
        <div className="font-display text-sm uppercase tracking-widest text-[var(--accent-amber)]">
          {this.props.label ?? "Component"} unavailable
        </div>
        <div className="max-w-md text-xs text-[var(--text-dim)]">
          This panel hit an error and was isolated so the rest of the app keeps working.
        </div>
        <div className="font-mono text-[10px] text-[var(--text-dim)]">{this.state.message}</div>
      </div>
    );
  }
}
