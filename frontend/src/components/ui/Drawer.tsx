import { useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

import { useFocusTrap } from '../../hooks/useFocusTrap'
import { cn } from '../../lib/cn'

export interface DrawerProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
  /** `right` for detail panels, `left` for navigation. */
  side?: 'left' | 'right'
}

/**
 * A side panel for content that would crowd the page but does not deserve a
 * route of its own — alert detail, filters, the mobile nav.
 */
export function Drawer({ open, onClose, title, children, footer, side = 'right' }: DrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  useFocusTrap(panelRef, open, onClose)

  if (!open) return null

  return createPortal(
    <div className="fixed inset-0 z-overlay">
      <div
        className="absolute inset-0 bg-navy-900/40 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden="true"
      />

      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        tabIndex={-1}
        className={cn(
          'absolute inset-y-0 flex w-full max-w-md flex-col bg-surface-raised shadow-raised',
          'animate-slide-in-right',
          side === 'right' ? 'right-0' : 'left-0',
        )}
      >
        <header className="flex items-center justify-between gap-4 border-b border-border-subtle px-5 py-4">
          <h2 id="drawer-title" className="text-h2 font-semibold text-text-primary">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close panel"
            className="-mr-1.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-text-muted hover:bg-surface-sunken hover:text-text-primary"
          >
            <X className="h-4.5 w-4.5" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-5">{children}</div>

        {footer && (
          <footer className="flex flex-wrap justify-end gap-2 border-t border-border-subtle px-5 py-4">
            {footer}
          </footer>
        )}
      </div>
    </div>,
    document.body,
  )
}
