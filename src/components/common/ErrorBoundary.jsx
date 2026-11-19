import { Component } from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';
import { Button } from './Button';

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('NIYANTRA Uncaught Error Boundary caught:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-50 dark:bg-[#0B0F19] text-slate-900 dark:text-slate-100 flex items-center justify-center p-6">
          <div className="max-w-md w-full p-6 sm:p-8 rounded-2xl bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 shadow-modal text-center space-y-4">
            <div className="w-12 h-12 rounded-xl bg-rose-50 dark:bg-rose-950/50 text-rose-600 dark:text-rose-400 mx-auto flex items-center justify-center">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <h2 className="text-lg font-bold">Something went wrong</h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              An unexpected rendering issue occurred in NIYANTRA. Your task data is safely preserved in local storage.
            </p>
            {this.state.error?.message && (
              <pre className="text-[11px] p-2 rounded-lg bg-slate-100 dark:bg-slate-900 text-rose-600 dark:text-rose-400 font-mono text-left overflow-x-auto max-h-24">
                {this.state.error.message}
              </pre>
            )}
            <div className="pt-2">
              <Button
                variant="primary"
                size="md"
                icon={RotateCcw}
                onClick={this.handleReset}
                className="w-full"
              >
                Reload Workspace
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
