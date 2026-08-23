import { ShieldCheck } from 'lucide-react'
import { useState } from 'react'

import { cn } from '../../lib/cn'
import { HeroVisitCard } from './HeroVisitCard'

/**
 * The nurse photograph beside the home page headline.
 *
 * Two shapes, because the two kinds of source photo need opposite treatment:
 *
 *  - `framed` (the default) is an ordinary rectangular photo that brings its own
 *    background. It gets a rounded frame, `object-cover`, and a green wash tying
 *    it to the hero — without that wash a cool-toned stock photo sits on the
 *    green band looking pasted on, which is the usual tell.
 *  - `cutout` is a subject isolated on transparency. It gets `object-contain`
 *    over the blobs, with nothing laid over the top of it.
 *
 * The blobs are CSS, not SVG: asymmetric `border-radius`
 * (`60% 40% 30% 70% / 60% 30% 70% 40%`) gives a soft irregular form that scales
 * with the container and costs nothing to render.
 *
 * ---------------------------------------------------------------------------
 *  ON THE PHOTOGRAPH ITSELF — read before changing the sources.
 * ---------------------------------------------------------------------------
 * A portrait beside "someone checks on your parents" reads as DoorDoctor staff,
 * so the image needs to be one of:
 *
 *   - a real DoorDoctor nurse who has given written consent to appear, or
 *   - a stock photo under a licence that permits commercial use.
 *
 * A watermarked agency preview is a *comp*: agencies permit it for internal
 * layout and mockups, which is what this is while the site runs on localhost. It
 * is not licensed for a public site. **Do not strip the watermark** — that is
 * what turns a permitted comp into infringement. Replace the file with a
 * licensed or owned photo before this goes live.
 */

type Fit = 'framed' | 'cutout'

/**
 * Tried in order. Saving a photo out of a browser gives you whatever the source
 * was — an agency preview is a JPEG, a cut-out is a PNG — so pinning the code to
 * one extension means the file lands in `public/` and silently does nothing.
 * Drop in `nurse-hero.` plus any of these and it is picked up.
 */
const DEFAULT_SOURCES = [
  // Alpha-capable formats first: the hero art is a cut-out, and WebP carries
  // transparency at a fraction of PNG's weight. JPEG stays last for a framed
  // photograph, which is the only case with no transparency to preserve.
  '/nurse-hero.webp',
  '/nurse-hero.png',
  '/nurse-hero.jpg',
  '/nurse-hero.jpeg',
]

interface Props {
  /** Candidate paths, tried in order. Defaults to `/nurse-hero.*`. */
  sources?: string[]
  alt?: string
  /** `framed` for a normal photo, `cutout` for one on transparency. */
  fit?: Fit
}

export function NurseHero({
  sources = DEFAULT_SOURCES,
  alt = 'DoorDoctor nurses',
  fit = 'framed',
}: Props) {
  const [index, setIndex] = useState(0)
  const src = sources[index]

  // Every candidate 404'd: show the visit card rather than a broken frame. A
  // hero is the worst place on the site for a missing asset.
  if (!src) return <HeroVisitCard />

  const framed = fit === 'framed'

  return (
    <div
      className={cn(
        'relative w-full',
        framed
          // 3:2 for a framed photo — group shots and most stock photography are
          // landscape, and a 4:3 window crops the people at the edges away.
          ? 'mx-auto max-w-md aspect-[3/2]'
          // A cut-out has no frame to contain it, so it is allowed to run wider
          // than its column and sit off to the right, which is what stops it
          // reading as a picture dropped into a slot. The hero clips the
          // overflow, so nothing here can cause a horizontal scrollbar.
          : 'mx-auto aspect-[3/2] max-w-xl xl:mx-0 xl:translate-x-8 xl:scale-[1.22]',
      )}
    >
      {/* Blobs, offset so they read as one composition rather than two circles.
          On `framed` they sit proud of the frame's corners; behind a cut-out
          they are the only thing giving the figures a ground to stand on. */}
      <div
        aria-hidden="true"
        className="absolute -left-5 -top-5 h-[70%] w-[70%] bg-white/15"
        style={{ borderRadius: '60% 40% 30% 70% / 60% 30% 70% 40%' }}
      />
      <div
        aria-hidden="true"
        className="absolute -bottom-6 -right-5 h-[58%] w-[58%] bg-brand-400/25"
        style={{ borderRadius: '38% 62% 63% 37% / 41% 44% 56% 59%' }}
      />

      {/* A soft bloom directly behind the group. Without it a cut-out floats:
          there is no contact shadow and no change in the field behind it, which
          is precisely what makes an image look pasted on. */}
      {!framed && (
        <div
          aria-hidden="true"
          className="absolute left-1/2 top-1/2 h-[85%] w-[85%] -translate-x-1/2 -translate-y-1/2 rounded-full bg-brand-400/25 blur-3xl"
        />
      )}

      <div
        className={cn(
          'absolute inset-0',
          framed && 'overflow-hidden rounded-2xl shadow-raised ring-1 ring-white/20',
        )}
      >
        <img
          // Keyed so React swaps the element rather than reusing one that has
          // already errored — without this the next candidate never loads.
          key={src}
          src={src}
          alt={alt}
          onError={() => setIndex((i) => i + 1)}
          className={cn(
            'h-full w-full',
            framed ? 'object-cover' : 'object-contain object-bottom drop-shadow-2xl',
          )}
        />

        {/* The blend. A green multiply at low strength pulls a cool stock photo
            toward the hero's palette, and the bottom gradient gives the chip
            something to sit on instead of floating over a busy image. Only on
            `framed` — a cut-out subject must never be tinted. */}
        {framed && (
          <>
            {/* 18%, not more: enough to pull a cool photo toward the hero,
                little enough that skin tones do not turn green. */}
            <div
              aria-hidden="true"
              className="absolute inset-0 bg-brand-700/[0.18] mix-blend-multiply"
            />
            <div
              aria-hidden="true"
              className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-navy-900/60 to-transparent"
            />
          </>
        )}
      </div>

      {/* One small proof point, anchored to the photo. */}
      <div
        className={cn(
          'absolute flex items-center gap-2 rounded-full bg-surface-raised px-3.5 py-2 shadow-raised',
          framed ? 'bottom-4 left-4' : 'bottom-8 left-0 xl:bottom-12',
        )}
      >
        <ShieldCheck className="h-4 w-4 shrink-0 text-brand-600" aria-hidden="true" />
        <span className="text-small font-semibold text-text-primary">Credentials verified</span>
      </div>
    </div>
  )
}
