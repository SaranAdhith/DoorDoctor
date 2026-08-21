import {
  Activity,
  Bell,
  CalendarDays,
  LayoutDashboard,
  Pill,
  Stethoscope,
  Users,
  type LucideIcon,
} from 'lucide-react'

import type { Role } from '../../types'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** Shown in the mobile bottom bar. At most four per role. */
  primary?: boolean
}

export interface NavSection {
  /** Omitted for the first, unlabelled group. */
  title?: string
  items: NavItem[]
}

/**
 * Grouped navigation, one tree per role.
 *
 * Sections exist so the sidebar stays readable as Phases 4-10 add pages;
 * `primary` marks the four destinations that reach the mobile bottom bar.
 */
export const NAV_BY_ROLE: Record<Role, NavSection[]> = {
  family: [
    {
      items: [
        { to: '/family/dashboard', label: 'Dashboard', icon: LayoutDashboard, primary: true },
        { to: '/family/medications', label: 'Medications', icon: Pill, primary: true },
        { to: '/family/alerts', label: 'Alerts', icon: Bell, primary: true },
      ],
    },
  ],
  nurse: [
    {
      items: [{ to: '/nurse/visits', label: "Today's visits", icon: CalendarDays, primary: true }],
    },
  ],
  admin: [
    {
      items: [{ to: '/admin/dashboard', label: 'Dashboard', icon: LayoutDashboard, primary: true }],
    },
    {
      title: 'Operations',
      items: [
        { to: '/admin/visits', label: 'Visits', icon: CalendarDays, primary: true },
        { to: '/admin/alerts', label: 'Alerts', icon: Bell, primary: true },
      ],
    },
    {
      title: 'Directory',
      items: [
        { to: '/admin/patients', label: 'Patients', icon: Activity, primary: true },
        { to: '/admin/nurses', label: 'Nurses', icon: Stethoscope },
      ],
    },
  ],
}

export const ROLE_LABELS: Record<Role, string> = {
  family: 'Family Member',
  nurse: 'Nurse',
  admin: 'Admin',
}

export const ROLE_ICONS: Record<Role, LucideIcon> = {
  family: Users,
  nurse: Stethoscope,
  admin: LayoutDashboard,
}

/** Flattened, in sidebar order — used by the mobile bottom bar. */
export function primaryNavItems(role: Role): NavItem[] {
  return NAV_BY_ROLE[role]
    .flatMap((section) => section.items)
    .filter((item) => item.primary)
    .slice(0, 4)
}
