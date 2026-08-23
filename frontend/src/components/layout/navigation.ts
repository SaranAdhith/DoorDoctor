import {
  Activity,
  Bell,
  CalendarDays,
  CreditCard,
  FileText,
  FlaskConical,
  HeartPulse,
  Inbox,
  LayoutDashboard,
  MessageCircleQuestion,
  Pill,
  ShieldAlert,
  Stethoscope,
  TrendingUp,
  Users,
  UsersRound,
  Video,
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
        // Primary, and Medications yields its bottom-bar slot for it: asking a
        // question in your own words is the point of the product, and the
        // mobile bar holds four.
        { to: '/family/assistant', label: 'Ask DoorDoctor', icon: MessageCircleQuestion, primary: true },
        { to: '/family/medications', label: 'Medications', icon: Pill },
        { to: '/family/alerts', label: 'Alerts', icon: Bell, primary: true },
        { to: '/family/reports', label: 'Reports', icon: FileText },
      ],
    },
    {
      // The safety score, the care manager and the mood check live together
      // under Care: they are one question — "how are they, and who is looking
      // after them?" — and splitting them across three nav items would make a
      // family hunt for the answer.
      title: 'Health',
      items: [
        { to: '/family/care', label: 'Care', icon: HeartPulse },
        { to: '/family/labs', label: 'Tests', icon: FlaskConical },
        { to: '/family/consults', label: 'Doctor consults', icon: Video },
      ],
    },
    {
      title: 'Account',
      items: [{ to: '/family/plan', label: 'My Plan', icon: CreditCard, primary: true }],
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
        { to: '/admin/escalations', label: 'Escalations', icon: ShieldAlert },
        { to: '/admin/assistant', label: 'Ask DoorDoctor', icon: MessageCircleQuestion },
      ],
    },
    {
      title: 'Clinical',
      items: [
        { to: '/admin/labs', label: 'Labs', icon: FlaskConical },
        { to: '/admin/care', label: 'Care managers', icon: UsersRound },
      ],
    },
    {
      title: 'Directory',
      items: [
        { to: '/admin/patients', label: 'Patients', icon: Activity, primary: true },
        { to: '/admin/nurses', label: 'Nurses', icon: Stethoscope },
      ],
    },
    {
      title: 'Business',
      items: [
        { to: '/admin/subscriptions', label: 'Subscriptions', icon: CreditCard },
        { to: '/admin/revenue', label: 'Revenue', icon: TrendingUp },
        { to: '/admin/leads', label: 'Leads', icon: Inbox },
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
