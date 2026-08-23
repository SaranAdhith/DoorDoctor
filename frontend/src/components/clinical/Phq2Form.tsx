import { useState } from 'react'

import type { ScreeningInstrument } from '../../types'
import { Button, RadioGroup } from '../ui'

/**
 * The PHQ-2 mood screen, as the nurse's visit screen renders it (§4.7).
 *
 * Every string here — the preamble, the two questions, the four answer labels,
 * the disclaimer — is **served** by the backend from `core/clinical.py`. PHQ-2
 * is a published instrument, and its wording is not something a frontend gets
 * to paraphrase to fit a layout.
 *
 * The disclaimer is shown before the questions rather than after the result,
 * because a screening tool that looks like a diagnosis does its harm at the
 * moment somebody answers it, not at the moment they read the score.
 */
export function Phq2Form({
  instrument,
  submitting,
  onSubmit,
}: {
  instrument: ScreeningInstrument
  submitting?: boolean
  onSubmit: (answers: number[]) => void
}) {
  const [answers, setAnswers] = useState<(number | null)[]>(
    instrument.questions.map(() => null),
  )

  const complete = answers.every((answer) => answer !== null)

  const options = instrument.answers.map((answer) => ({
    value: String(answer.value),
    label: answer.label,
  }))

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        if (complete) onSubmit(answers as number[])
      }}
      className="space-y-5"
    >
      <p className="text-small text-text-secondary">{instrument.preamble}</p>

      {instrument.questions.map((question, index) => (
        <RadioGroup
          key={question}
          name={`phq2-${index}`}
          legend={`${index + 1}. ${question}`}
          options={options}
          value={answers[index] === null ? '' : String(answers[index])}
          onChange={(value) =>
            setAnswers((current) => {
              const next = [...current]
              next[index] = Number(value)
              return next
            })
          }
        />
      ))}

      <p className="rounded-md bg-surface-sunken p-3 text-caption text-text-secondary">
        {instrument.disclaimer}
      </p>

      <Button type="submit" disabled={!complete || submitting}>
        {submitting ? 'Recording…' : 'Record mood check'}
      </Button>
    </form>
  )
}
