type Toast = { id: number; text: string; tone?: 'info' | 'error' }

export function ToastStack({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: number) => void }) {
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <button
          key={toast.id}
          className={`toast toast-${toast.tone || 'info'}`}
          onClick={() => onDismiss(toast.id)}
          type="button"
        >
          {toast.text}
        </button>
      ))}
    </div>
  )
}
