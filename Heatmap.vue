<script setup>
// Study calendar: one square per day, columns are weeks. Sequential single-hue scale relative to the daily goal.
import { computed, ref } from 'vue'

const props = defineProps({ days: { type: Array, required: true }, goal: { type: Number, default: 25 } })
const hover = ref(null)
const levels = [
  { label: 'No study', color: 'var(--seq-0)' },
  { label: 'Under half the goal', color: 'var(--seq-1)' },
  { label: 'Over half the goal', color: 'var(--seq-2)' },
  { label: 'Goal met', color: 'var(--seq-3)' },
  { label: 'Double the goal', color: 'var(--seq-5)' },
]
function level(m) {
  if (!m) return 0
  if (m < props.goal / 2) return 1
  if (m < props.goal) return 2
  if (m < props.goal * 2) return 3
  return 4
}
const cells = computed(() => {
  const first = new Date(props.days[0]?.date + 'T00:00:00')
  const offset = (first.getDay() + 6) % 7 // Monday-first rows
  return props.days.map((d, i) => {
    const k = i + offset
    return { ...d, col: Math.floor(k / 7), row: k % 7, lvl: level(d.minutes) }
  })
})
const cols = computed(() => (cells.value.at(-1)?.col ?? 0) + 1)
const S = 13
const G = 3
const fmt = new Intl.DateTimeFormat(undefined, { weekday: 'short', day: 'numeric', month: 'short' })
</script>

<template>
  <div class="heat">
    <div class="scroll">
      <svg :width="cols * (S + G) + 26" :height="7 * (S + G) + 4" role="img" aria-label="Daily study calendar">
        <text v-for="(d, i) in ['Mon', '', 'Wed', '', 'Fri', '', '']" :key="i" x="0" :y="i * (S + G) + S - 2" class="day">{{ d }}</text>
        <rect v-for="c in cells" :key="c.date" :x="26 + c.col * (S + G)" :y="c.row * (S + G)" :width="S" :height="S" rx="3"
              :fill="levels[c.lvl].color" :stroke="hover === c ? 'var(--ink)' : 'none'" @mouseenter="hover = c" @mouseleave="hover = null">
          <title>{{ fmt.format(new Date(c.date + 'T00:00:00')) }}: {{ c.minutes }} min{{ c.met ? ' (goal met)' : '' }}</title>
        </rect>
      </svg>
    </div>
    <div class="row small muted foot">
      <span v-if="hover">{{ fmt.format(new Date(hover.date + 'T00:00:00')) }}: <strong>{{ hover.minutes }} min</strong></span>
      <span v-else>Hover a day for details</span>
      <span class="spacer" />
      <span v-for="l in levels" :key="l.label" class="key"><span class="sw" :style="{ background: l.color }" />{{ l.label }}</span>
    </div>
  </div>
</template>

<style scoped>
.scroll { overflow-x: auto; padding-bottom: 4px; }
.day { fill: var(--muted); font-size: 10px; }
.foot { margin-top: 6px; gap: 6px 12px; }
.key { display: inline-flex; align-items: center; gap: 5px; }
.sw { width: 11px; height: 11px; border-radius: 3px; display: inline-block; }
</style>
