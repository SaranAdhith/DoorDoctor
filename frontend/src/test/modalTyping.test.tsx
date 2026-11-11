import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'

import { Modal, Textarea } from '../components/ui'

/**
 * A dialog with a text field, opened by a parent that passes an inline
 * `onClose` — exactly how the document reject dialog is written. Typing
 * re-renders the parent, which hands the dialog a new `onClose` each time.
 */
function RejectDialog({ onEscape }: { onEscape?: () => void }) {
  const [open, setOpen] = useState(true)
  const [reason, setReason] = useState('')
  return (
    <Modal
      open={open}
      onClose={() => {
        onEscape?.()
        setOpen(false)
      }}
      title="Reject this document"
    >
      <Textarea label="Why?" value={reason} onChange={(e) => setReason(e.target.value)} />
    </Modal>
  )
}

describe('Modal focus while typing', () => {
  // jsdom has no layout, so `offsetParent` is always null and the focus trap
  // would treat every control as hidden. In a browser they are visible — the
  // close button included, which is where focus was being dragged to. Make
  // them visible here too, or the bug can't be reproduced.
  const original = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetParent')
  beforeAll(() => {
    Object.defineProperty(HTMLElement.prototype, 'offsetParent', {
      configurable: true,
      get() {
        return document.body
      },
    })
  })
  afterAll(() => {
    if (original) Object.defineProperty(HTMLElement.prototype, 'offsetParent', original)
  })

  it('keeps focus in the text field across keystrokes', () => {
    render(<RejectDialog />)
    const field = screen.getByLabelText('Why?')
    field.focus()
    for (const value of ['W', 'Wr', 'Wro', 'Wrong patient']) {
      fireEvent.change(field, { target: { value } })
      expect(document.activeElement).toBe(field)
    }
    expect(field).toHaveValue('Wrong patient')
  })

  it('still closes on Escape with the latest onClose', () => {
    const onEscape = vi.fn()
    render(<RejectDialog onEscape={onEscape} />)
    fireEvent.change(screen.getByLabelText('Why?'), { target: { value: 'x' } })
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onEscape).toHaveBeenCalledOnce()
    expect(screen.queryByLabelText('Why?')).not.toBeInTheDocument()
  })
})
