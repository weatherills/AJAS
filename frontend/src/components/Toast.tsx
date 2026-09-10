type Toast = {
  id: number
  text: string
  tone?: 'info' | 'error'
  actionLabel?: string
  onAction?: () => void
}

export function ToastStack({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: number) => void }) {
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((toast) =>
        toast.actionLabel && toast.onAction ? (
          <div key={toast.id} className={`toast toast-${toast.tone || 'info'} toast-with-action`}>
            <span>{toast.text}</span>
            <button
              type="button"
              className="toast-action"
              onClick={() => {
                toast.onAction?.()
                onDismiss(toast.id)
              }}
            >
              {toast.actionLabel}
            </button>
          </div>
        ) : (
          <button
            key={toast.id}
            className={`toast toast-${toast.tone || 'info'}`}
            onClick={() => onDismiss(toast.id)}
            type="button"
          >
            {toast.text}
          </button>
        ),
      )}
    </div>
  )
}
