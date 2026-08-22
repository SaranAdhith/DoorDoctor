import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { publicApi } from '../api/public'
import { PricingGrid } from '../components/public/PricingGrid'
import type { Plan, PublicPlans } from '../types'

vi.mock('../api/public', () => ({
  publicApi: { plans: vi.fn(), submitLead: vi.fn() },
}))

const plans = vi.mocked(publicApi.plans)

function plan(overrides: Partial<Plan>): Plan {
  return {
    id: 1,
    code: 'care_plus',
    name: 'Care Plus',
    audience: 'individual',
    tagline: 'Twice-weekly visits.',
    monthly_paise: 350_000,
    annual_paise: 3_500_000,
    recommended: false,
    unit_label: null,
    unit_included: null,
    unit_paise: null,
    unit_period: null,
    entitlements: {
      visits_per_month: 8,
      telemedicine_per_month: 1,
      lab_panels_per_year: 2,
      care_manager: 'shared',
      care_manager_ratio: 20,
      report_cadence: 'weekly',
      family_seats: 4,
      priority_escalation: false,
      ai_assistant: true,
    },
    ...overrides,
  }
}

function payload(overrides: Partial<PublicPlans> = {}): PublicPlans {
  return {
    plans: [plan({})],
    add_ons: [{ code: 'blood_panel', name: 'Blood panel', price_paise: 49_900, unit: 'per panel' }],
    annual_months_free: 2,
    ...overrides,
  }
}

function renderGrid(props: Partial<Parameters<typeof PricingGrid>[0]> = {}) {
  return render(
    <MemoryRouter>
      <PricingGrid audience="individual" {...props} />
    </MemoryRouter>,
  )
}

describe('PricingGrid', () => {
  beforeEach(() => {
    plans.mockReset()
  })

  it('renders the price the server sent, formatted for India', async () => {
    // The whole point of fetching prices is that no rupee figure is typed into
    // a component. This asserts the number on screen came from the payload.
    plans.mockResolvedValue(payload())
    renderGrid()

    expect(await screen.findByText('₹3,500')).toBeInTheDocument()
  })

  it('asks the server for the audience it was given', async () => {
    plans.mockResolvedValue(payload({ plans: [] }))
    renderGrid({ audience: 'institution' })

    await waitFor(() => expect(plans).toHaveBeenCalledWith('institution'))
  })

  it('marks the recommended plan from the data, not from a plan code', async () => {
    plans.mockResolvedValue(
      payload({
        plans: [plan({ code: 'essential', name: 'Essential', recommended: false }), plan({ recommended: true })],
      }),
    )
    renderGrid()

    expect(await screen.findByText(/recommended/i)).toBeInTheDocument()
  })

  it('takes the "months free" claim from the payload rather than stating one', async () => {
    plans.mockResolvedValue(payload({ annual_months_free: 3 }))
    renderGrid({ showCycleToggle: true })

    expect(await screen.findByText(/3 months are free/i)).toBeInTheDocument()
  })

  it('shows the annual price when the annual cycle is selected', async () => {
    plans.mockResolvedValue(payload())
    renderGrid({ showCycleToggle: true })
    fireEvent.click(await screen.findByRole('radio', { name: 'Annual' }))

    expect(await screen.findByText('₹35,000')).toBeInTheDocument()
  })

  it('renders the per-unit headline an organization plan is sold on', async () => {
    plans.mockResolvedValue(
      payload({
        plans: [
          plan({
            code: 'institution_15',
            name: 'Institutional 15',
            audience: 'institution',
            monthly_paise: 3_800_000,
            annual_paise: null,
            unit_label: 'resident',
            unit_included: 15,
            unit_paise: 8_400,
            unit_period: 'day',
          }),
        ],
      }),
    )
    renderGrid({ audience: 'institution' })

    expect(await screen.findByText('₹84 per resident per day')).toBeInTheDocument()
  })

  it('lists add-ons at the price the server sent', async () => {
    plans.mockResolvedValue(payload())
    renderGrid()

    expect(await screen.findByText('Blood panel')).toBeInTheDocument()
    expect(screen.getByText(/₹499/)).toBeInTheDocument()
  })

  it('offers a retry when the price list cannot be loaded', async () => {
    // A marketing page is still a page that loads data. Phase 2's rule —
    // skeleton, empty, error-with-retry — does not stop applying here.
    plans.mockRejectedValue(new Error('offline'))
    renderGrid()

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })
})
