<script setup>
// Column chart: one series, or stacked series separated by a 2px surface gap. Bars are capped at 24px,
// rounded only at the data end, and grow from one baseline. An optional reference line (e.g. the daily goal)
// shares the same axis: never a second axis.
import { computed, ref } from 'vue'

const props = defineProps({
  rows: { type: Array, required: true }, // [{ label, [seriesKey]: number }]
  series: { type: Array, required: true }, // [{ key, label, color }]
  refLine: { type: Object, default: null }, // { value, label }
  format: { type: Function, default: (v) => String(v) },
  height: { type: Number, default: 200 },
  labelFormat: { type: Function, default: (l) => l },
})
const W = 640
const pad = { l: 40, r: 8, t: 14, b: 26 }
const plotW = W - pad.l - pad.r
const plotH = computed(() => props.height - pad.t - pad.b)
const hover = ref(null)

// a clean tick step (1, 2, 5 or 10 times a power of ten), so the axis reads 0/10/20/30/40, never 0/13/25/38
function niceStep(v) {
  const p = 10 ** Math.floor(Math.log10(v))
  const n = v / p
  return Math.max(1, (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p)
}
const max = computed(() => {
  const tops = props.rows.map((r) => props.series.reduce((s, x) => s + (r[x.key] || 0), 0))
  return niceStep(Math.max(...tops, props.refLine?.value || 0, 4) / 4) * 4
})
const ticks = computed(() => [0, 1, 2, 3, 4].map((i) => (max.value * i) / 4))
const y = (v) => pad.t + plotH.value - (v / max.value) * plotH.value
const band = computed(() => plotW / Math.max(1, props.rows.length))
const barW = computed(() => Math.min(24, band.value * 0.62))
const every = computed(() => Math.ceil(props.rows.length / 8))

function roundedTop(x, y0, w, h, r) {
  if (h <= 0) return ''
  r = Math.min(r, h, w / 2)
  return `M${x},${y0 + h} V${y0 + r} Q${x},${y0} ${x + r},${y0} H${x + w - r} Q${x + w},${y0} ${x + w},${y0 + r} V${y0 + h} Z`
}
const bars = computed(() => props.rows.map((r, i) => {
  const cx = pad.l + band.value * i + band.value / 2
  let acc = 0
  const segs = []
  const nonzero = props.series.filter((s) => (r[s.key] || 0) > 0)
  for (const s of props.series) {
    const v = r[s.key] || 0
    if (!v) continue
    const top = y(acc + v)
    const bottom = y(acc)
    const isTop = s === nonzero[nonzero.length - 1]
    const h = Math.max(0, bottom - top - (acc > 0 ? 2 : 0))  // 2px surface gap between stacked segments
    segs.push({ key: s.key, color: s.color, d: isTop ? roundedTop(cx - barW.value / 2, top, barW.value, h, 4) : `M${cx - barW.value / 2},${top}h${barW.value}v${h}h${-barW.value}Z` })
    acc += v
  }
  return { cx, segs, row: r, i }
}))
const tip = computed(() => {
  if (hover.value === null) return null
  const b = bars.value[hover.value]
  return { left: `${(b.cx / W) * 100}%`, row: b.row }
})
</script>

<template>
  <div class="chart" @mouseleave="hover = null">
    <svg :viewBox="`0 0 ${W} ${height}`" width="100%" role="img" :aria-label="series.map((s) => s.label).join(', ')">
      <g class="grid">
        <line v-for="t in ticks" :key="t" :x1="pad.l" :x2="W - pad.r" :y1="y(t)" :y2="y(t)" />
      </g>
      <g class="axis">
        <text v-for="t in ticks" :key="'t' + t" :x="pad.l - 6" :y="y(t) + 4" text-anchor="end">{{ format(t) }}</text>
        <template v-for="b in bars" :key="'l' + b.i">
          <text v-if="b.i % every === 0" :x="b.cx" :y="height - 8" text-anchor="middle">{{ labelFormat(b.row.label) }}</text>
        </template>
      </g>
      <g>
        <g v-for="b in bars" :key="b.i" :opacity="hover === null || hover === b.i ? 1 : 0.55">
          <path v-for="s in b.segs" :key="s.key" :d="s.d" :fill="s.color" />
        </g>
      </g>
      <g v-if="refLine" class="ref">
        <line :x1="pad.l" :x2="W - pad.r" :y1="y(refLine.value)" :y2="y(refLine.value)" />
        <text :x="W - pad.r" :y="y(refLine.value) - 5" text-anchor="end">{{ refLine.label }}</text>
      </g>
      <rect v-for="b in bars" :key="'h' + b.i" :x="b.cx - band / 2" :y="pad.t" :width="band" :height="plotH" fill="transparent" @mouseenter="hover = b.i" @focus="hover = b.i" tabindex="-1" />
    </svg>
    <div v-if="tip" class="tip" :style="{ left: tip.left }">
      <strong>{{ labelFormat(tip.row.label) }}</strong>
      <div v-for="s in series" :key="s.key" class="tip-row"><span class="sw" :style="{ background: s.color }" />{{ s.label }}: {{ format(tip.row[s.key] || 0) }}</div>
    </div>
  </div>
</template>

<style scoped>
.chart { position: relative; margin-top: 8px; }
svg { display: block; overflow: visible; }
.grid line { stroke: var(--grid); stroke-width: 1; }
.axis text { fill: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.ref line { stroke: var(--ink-2); stroke-width: 1.5; stroke-dasharray: none; opacity: .6; }
.ref text { fill: var(--ink-2); font-size: 11px; font-weight: 700; }
.tip { position: absolute; top: 0; transform: translateX(-50%); background: var(--surface-solid); border: 1px solid var(--border); box-shadow: var(--shadow); border-radius: 10px; padding: 6px 10px; font-size: .8rem; pointer-events: none; white-space: nowrap; z-index: 2; }
.tip-row { display: flex; align-items: center; gap: 6px; color: var(--ink-2); }
.sw { width: 10px; height: 10px; border-radius: 3px; }
</style>
