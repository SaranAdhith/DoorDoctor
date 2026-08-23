import { cn } from '../../lib/cn'

/**
 * A live ECG trace, used as the rule that closes a hero.
 *
 * The waveform follows real rhythm-strip proportions rather than a decorative
 * zigzag, which is the whole difference between this reading as a monitor and
 * reading as a squiggle. At roughly 25mm/s a cardiac cycle is about 800ms, and
 * the QRS complex occupies only 80–100ms of it — so the spike is *narrow* and
 * most of the strip is flat isoelectric baseline. Evenly-spaced bumps across the
 * whole width are the tell that gives away a fake.
 *
 * Within one 400-unit beat:
 *   000–105  TP segment, flat
 *   105–140  P wave, small and rounded
 *   140–163  PR segment, flat
 *   163–178  QRS: small Q dip, sharp tall R, S below baseline
 *   178–200  ST segment, flat
 *   200–268  T wave, broad and asymmetric — slow up, faster down
 *   268–400  back to baseline
 *
 * The scroll is done in HTML rather than SVG: the strip is 200% wide, holds the
 * same waveform twice, and travels -50%. Percentage transforms on an HTML
 * element are unambiguous, where the same animation on an SVG `<g>` depends on
 * `transform-box` support. Travelling exactly one tile width means tile two
 * arrives where tile one started, so the loop has no seam.
 *
 * `vector-effect="non-scaling-stroke"` is what makes `preserveAspectRatio="none"`
 * safe: the waveform stretches horizontally to whatever width it is given, while
 * the stroke stays the weight it was drawn at instead of thickening with scale.
 *
 * The global `prefers-reduced-motion` rule in `index.css` stops both animations,
 * so a reader who asked for less motion gets a still trace. It is decorative and
 * `aria-hidden`; nothing here is a reading, and it must never be taken for one.
 */

export type EcgTone = 'on-green' | 'on-light'

const BEAT = 400
/** The box is 64 tall and the baseline sits at 26, well above the floor: the S
 *  wave is the lowest excursion and must never reach the bottom edge. */
const BASE = 26

function beat(o: number): string {
  const x = (n: number) => n + o
  return [
    `M ${x(0)} ${BASE}`,
    // TP segment — the long flat stretch that makes the beat read as a beat.
    `L ${x(105)} ${BASE}`,
    // P wave: atrial depolarisation. Small, rounded, never spiky.
    `C ${x(114)} ${BASE - 7}, ${x(131)} ${BASE - 7}, ${x(140)} ${BASE}`,
    `L ${x(163)} ${BASE}`,
    // QRS complex. Narrow by design — this is ~10% of the cycle.
    `L ${x(167)} ${BASE + 4}`,
    `L ${x(171)} ${BASE - 21}`,
    `L ${x(175)} ${BASE + 13}`,
    `L ${x(178)} ${BASE}`,
    // ST segment, flat.
    `L ${x(200)} ${BASE}`,
    // T wave: repolarisation. Asymmetric on purpose — gradual ascent, steeper
    // descent, which is what the real thing does.
    `C ${x(222)} ${BASE - 9}, ${x(248)} ${BASE - 10}, ${x(268)} ${BASE}`,
    `L ${x(BEAT)} ${BASE}`,
  ].join(' ')
}

const TRACE = [0, BEAT, BEAT * 2].map(beat).join(' ')

/**
 * Two palettes. On the green hero the trace is white and reads like a monitor;
 * on a light hero it has to be the brand green or there is nothing to see. The
 * stops are the same shape either way so the two look like one component.
 */
const STOPS: Record<EcgTone, [string, string]> = {
  'on-green': ['#eefaf0', '#ffffff'],
  'on-light': ['#249432', '#32B641'],
}

function Trace({ gradientId, tone }: { gradientId: string; tone: EcgTone }) {
  const [edge, middle] = STOPS[tone]
  return (
    <svg
      viewBox={`0 0 ${BEAT * 3} 64`}
      preserveAspectRatio="none"
      className="h-full w-1/2 shrink-0"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={edge} stopOpacity="0.5" />
          <stop offset="45%" stopColor={middle} stopOpacity="0.95" />
          <stop offset="100%" stopColor={edge} stopOpacity="0.5" />
        </linearGradient>
      </defs>

      {/* Bloom under the line — drawn heavy and faint, then the crisp trace on
          top. Cheaper and steadier than an SVG blur filter. */}
      <path
        d={TRACE}
        fill="none"
        stroke={`url(#${gradientId})`}
        strokeWidth={8}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.3}
        vectorEffect="non-scaling-stroke"
      />
      <path
        d={TRACE}
        fill="none"
        stroke={`url(#${gradientId})`}
        strokeWidth={2.25}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}

interface Props {
  className?: string
  tone?: EcgTone
}

export function EcgLine({ className, tone = 'on-green' }: Props) {
  return (
    // The root carries no position class of its own. `cn` is a plain join, so a
    // `relative` here would fight the `absolute` a caller passes in and win or
    // lose on stylesheet order rather than on intent — which is exactly how this
    // trace once ended up floating 96px above the bottom of the hero.
    <div className={cn('pointer-events-none w-full overflow-hidden', className)} aria-hidden="true">
      <div className="relative h-16 w-full">
        <div className="animate-ecg-scroll flex h-full w-[200%]">
          {/* Two identical tiles. Distinct gradient ids so the second is not
              painting with a definition scoped to the first. */}
          <Trace gradientId="ecg-a" tone={tone} />
          <Trace gradientId="ecg-b" tone={tone} />
        </div>

        {/* The monitor's cursor, parked on the baseline where the trace is
            newest — not floating at the vertical centre of the box. */}
        <span
          className="absolute right-5 flex h-3.5 w-3.5 items-center justify-center"
          style={{ top: `${(BASE / 64) * 100}%`, transform: 'translateY(-50%)' }}
        >
          <span
            className={cn(
              'animate-ecg-pulse absolute inline-flex h-full w-full rounded-full',
              tone === 'on-green' ? 'bg-white/70' : 'bg-brand-400/70',
            )}
          />
          <span
            className={cn(
              'relative inline-flex h-1.5 w-1.5 rounded-full',
              tone === 'on-green' ? 'bg-white' : 'bg-brand-600',
            )}
          />
        </span>
      </div>
    </div>
  )
}
