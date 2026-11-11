/** A small count on a menu item. Hidden at zero; "9+" past nine. */
export function NavBadge({ count, label }: { count: number; label: string }) {
  if (count <= 0) return null
  return (
    <span
      className="ml-auto inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-brand-600 px-1.5 text-[11px] font-bold leading-5 text-white"
      aria-label={`${count} ${label}`}
    >
      {count > 9 ? '9+' : count}
    </span>
  )
}
