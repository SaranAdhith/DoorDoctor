import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { SegmentedControl } from '../components/ui/SegmentedControl'

const OPTIONS = [
  { value: 'family', label: 'Family' },
  { value: 'nurse', label: 'Nurse' },
  { value: 'admin', label: 'Admin' },
] as const

function renderControl(value: 'family' | 'nurse' | 'admin', onChange = vi.fn()) {
  render(
    <SegmentedControl
      legend="I am signing in as"
      value={value}
      options={OPTIONS}
      onChange={onChange}
    />,
  )
  return onChange
}

describe('SegmentedControl', () => {
  it('marks only the selected segment as checked', () => {
    renderControl('nurse')
    expect(screen.getByRole('radio', { name: 'Nurse' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Family' })).not.toBeChecked()
  })

  it('is a single tab stop', () => {
    // A radiogroup takes one tab stop and arrow keys move inside it.
    renderControl('nurse')
    expect(screen.getByRole('radio', { name: 'Nurse' })).toHaveAttribute('tabindex', '0')
    expect(screen.getByRole('radio', { name: 'Family' })).toHaveAttribute('tabindex', '-1')
    expect(screen.getByRole('radio', { name: 'Admin' })).toHaveAttribute('tabindex', '-1')
  })

  it('moves to the next segment on ArrowRight', () => {
    const onChange = renderControl('family')
    fireEvent.keyDown(screen.getByRole('radio', { name: 'Family' }), { key: 'ArrowRight' })
    expect(onChange).toHaveBeenCalledWith('nurse')
  })

  it('wraps from the first segment to the last on ArrowLeft', () => {
    const onChange = renderControl('family')
    fireEvent.keyDown(screen.getByRole('radio', { name: 'Family' }), { key: 'ArrowLeft' })
    expect(onChange).toHaveBeenCalledWith('admin')
  })

  it('jumps to the ends with Home and End', () => {
    const onChange = renderControl('nurse')
    const nurse = screen.getByRole('radio', { name: 'Nurse' })

    fireEvent.keyDown(nurse, { key: 'End' })
    expect(onChange).toHaveBeenCalledWith('admin')

    fireEvent.keyDown(nurse, { key: 'Home' })
    expect(onChange).toHaveBeenCalledWith('family')
  })

  it('selects on click', () => {
    const onChange = renderControl('family')
    fireEvent.click(screen.getByRole('radio', { name: 'Admin' }))
    expect(onChange).toHaveBeenCalledWith('admin')
  })
})
