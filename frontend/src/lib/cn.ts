/**
 * Joins class names, dropping anything falsy.
 *
 * Deliberately not a Tailwind-aware merger: the primitives own their base
 * classes and callers append, so conflicts are a code-review problem rather
 * than a runtime one.
 */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ')
}
