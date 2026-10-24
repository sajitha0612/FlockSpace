<script setup>
// One-series line (2px) with 8px end/point markers ringed in the surface colour, on a 0-100 scale.
import { computed, ref } from 'vue'

const props = defineProps({
  points: { type: Array, required: true }, // [{ label, value, note }]
  color: { type: String, default: 'var(--series-1)' },
  height: { type: Number, default: 200 },
  suffix: { type: String, default: '%' },
})
const W = 640
const pad = { l: 40, r: 14, t: 14, b: 26 }
const plotW = W - pad.l - pad.r
const plotH = computed(() => props.height - pad.t - pad.b)
const hover = ref(null)
const x = (i) => pad.l + (props.points.length <= 1 ? plotW / 2 : (plotW * i) / (props.points.length - 1))
const y = (v) => pad.t + plotH.value - (v / 100) * plotH.value
const path = computed(() => props.points.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p.value)}`).join(' '))
const area = computed(() => props.points.length > 1 ? `${path.value} L${x(props.points.length - 1)},${y(0)} L${x(0)},${y(0)} Z` : '')
const every = computed(() => Math.ceil(props.points.length / 7))
</script>

<template>
  <div class="chart" @mouseleave="hover = null">
    <svg :viewBox="`0 0 ${W} ${height}`" width="100%" role="img" aria-label="Accuracy over time">
      <g class="grid"><line v-for="t in [0, 25, 50, 75, 100]" :key="t" :x1="pad.l" :x2="W - pad.r" :y1="y(t)" :y2="y(t)" /></g>
      <g class="axis">
        <text v-for="t in [0, 25, 50, 75, 100]" :key="'t' + t" :x="pad.l - 6" :y="y(t) + 4" text-anchor="end">{{ t }}{{ suffix }}</text>
        <template v-for="(p, i) in points" :key="'l' + i">
          <text v-if="i % every === 0" :x="x(i)" :y="height - 8" text-anchor="middle">{{ p.label }}</text>
        </template>
      </g>
      <path :d="area" :fill="color" opacity=".1" />
      <path :d="path" fill="none" :stroke="color" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
      <circle v-for="(p, i) in points" :key="i" :cx="x(i)" :cy="y(p.value)" :r="hover === i ? 6 : 4" :fill="color" stroke="var(--surface)" stroke-width="2" />
      <text v-if="points.length" :x="x(points.length - 1)" :y="y(points[points.length - 1].value) - 10" text-anchor="end" class="end">{{ points[points.length - 1].value }}{{ suffix }}</text>
      <rect v-for="(p, i) in points" :key="'h' + i" :x="x(i) - Math.max(8, plotW / Math.max(1, points.length) / 2)" :y="pad.t" :width="Math.max(16, plotW / Math.max(1, points.length))" :height="plotH" fill="transparent" @mouseenter="hover = i" />
    </svg>
    <div v-if="hover !== null" class="tip" :style="{ left: `${(x(hover) / W) * 100}%` }">
      <strong>{{ points[hover].value }}{{ suffix }}</strong> <span class="muted">{{ points[hover].label }}</span>
      <div v-if="points[hover].note" class="muted">{{ points[hover].note }}</div>
    </div>
  </div>
</template>

<style scoped>
.chart { position: relative; margin-top: 8px; }
svg { display: block; overflow: visible; }
.grid line { stroke: var(--grid); stroke-width: 1; }
.axis text { fill: var(--muted); font-size: 11px; }
.end { fill: var(--ink); font-size: 12px; font-weight: 800; }
.tip { position: absolute; top: 0; transform: translateX(-50%); background: var(--surface-solid); border: 1px solid var(--border); box-shadow: var(--shadow); border-radius: 10px; padding: 6px 10px; font-size: .8rem; pointer-events: none; white-space: nowrap; }
</style>
