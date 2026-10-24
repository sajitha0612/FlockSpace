<script setup>
// A personal nest that fills with twigs as progress grows (0-100). skin: nest_twig | nest_moss | nest_golden | nest_legendary
import { computed } from 'vue'

const props = defineProps({
  progress: { type: Number, default: 0 },
  skin: { type: String, default: 'nest_twig' },
  size: { type: Number, default: 140 },
  label: { type: String, default: '' },
})
const SKINS = {
  nest_twig: { base: '#a8713a', light: '#c8925a', dark: '#7a4e25' },
  nest_moss: { base: '#7a8a3a', light: '#9fb55a', dark: '#55621f' },
  nest_golden: { base: '#d99a1c', light: '#f3c95a', dark: '#a8700c' },
  nest_legendary: { base: '#8e5bd0', light: '#f3c95a', dark: '#5a3290' },
}
const s = computed(() => SKINS[props.skin] || SKINS.nest_twig)
const pct = computed(() => Math.max(0, Math.min(100, props.progress)))
// twigs drawn in rows: more progress, more twigs, so the nest visibly grows
const twigs = computed(() => {
  const n = Math.round((pct.value / 100) * 18)
  const out = []
  for (let i = 0; i < n; i++) {
    const row = Math.floor(i / 6)
    const col = i % 6
    const y = 92 - row * 9
    const x = 30 + col * 14 + (row % 2) * 6
    out.push({ x1: x - 10, y1: y + (col % 2 ? 3 : -2), x2: x + 12, y2: y + (col % 2 ? -3 : 2), light: (i + row) % 3 === 0 })
  }
  return out
})
</script>

<template>
  <svg :width="size" :height="size * 0.75" viewBox="0 0 140 105" role="img" :aria-label="label || `Nest ${pct}% built`">
    <defs>
      <radialGradient :id="`glow-${skin}`" cx="50%" cy="60%" r="60%">
        <stop offset="0%" :stop-color="skin === 'nest_twig' || skin === 'nest_moss' ? 'transparent' : '#fff3c4'" stop-opacity=".8" />
        <stop offset="100%" stop-color="transparent" />
      </radialGradient>
    </defs>
    <ellipse cx="70" cy="70" rx="68" ry="34" :fill="`url(#glow-${skin})`" />
    <!-- bowl outline: always shown, so an empty nest reads as "to be built" -->
    <path d="M14 70 Q70 128 126 70" fill="none" :stroke="s.dark" stroke-width="3" stroke-dasharray="5 5" opacity=".45" />
    <ellipse cx="70" cy="70" rx="56" ry="13" fill="none" :stroke="s.dark" stroke-width="2" stroke-dasharray="4 5" opacity=".35" />
    <g stroke-linecap="round">
      <line v-for="(t, i) in twigs" :key="i" :x1="t.x1" :y1="t.y1" :x2="t.x2" :y2="t.y2" :stroke="t.light ? s.light : s.base" stroke-width="4.5" />
    </g>
    <g v-if="pct >= 100">
      <path d="M14 70 Q70 124 126 70 Q70 92 14 70 Z" :fill="s.base" />
      <ellipse cx="70" cy="70" rx="56" ry="13" :fill="s.dark" />
      <path d="M16 70 Q70 60 124 70" fill="none" :stroke="s.light" stroke-width="3" />
      <path d="M20 78 Q70 104 120 78" fill="none" :stroke="s.light" stroke-width="2.5" />
      <path d="M30 88 Q70 108 110 88" fill="none" :stroke="s.dark" stroke-width="2" />
      <g v-if="skin === 'nest_legendary'" fill="#f3c95a"><circle cx="40" cy="80" r="3" /><circle cx="70" cy="90" r="3.5" /><circle cx="100" cy="80" r="3" /></g>
    </g>
  </svg>
</template>
