<script setup>
// The student's bird, drawn in SVG from their equipped items. mood: idle | happy | sad | thinking | achievement | notify
import { computed } from 'vue'

const props = defineProps({
  bird: { type: Object, default: () => ({}) },
  size: { type: Number, default: 96 },
  mood: { type: String, default: 'idle' },
  framed: { type: Boolean, default: false },
  label: { type: String, default: '' },
})

const COLORS = {
  sparrow: { body: '#8a5a3b', dark: '#5e3b24', belly: '#f3e6d3', cheek: '#f2a3a0' },
  bluebird: { body: '#3d6fb6', dark: '#274d85', belly: '#f2d9b8', cheek: '#f2a3a0' },
  robin: { body: '#7a5236', dark: '#4f3421', belly: '#e0703c', cheek: '#f6c2a0' },
  goldfinch: { body: '#e8b923', dark: '#2b2b2b', belly: '#fff3c4', cheek: '#f2a3a0' },
}
const FRAMES = { frame_leaf: '#4f9a5c', frame_sky: '#5aa0e0', frame_gold: '#d99a1c' }
const c = computed(() => COLORS[props.bird?.color] || COLORS.sparrow)
const acc = computed(() => props.bird?.accessory)
const outfit = computed(() => props.bird?.outfit)
const frame = computed(() => FRAMES[props.bird?.frame] || FRAMES.frame_leaf)
const sparkles = computed(() => props.mood === 'achievement' || (props.mood === 'happy' && props.bird?.animation === 'anim_sparkle'))
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 120 120" :class="['bird', `m-${mood}`]" role="img" :aria-label="label || 'Bird avatar'">
    <circle v-if="framed" cx="60" cy="60" r="57" :fill="'var(--surface-2)'" :stroke="frame" stroke-width="5" />
    <g class="whole">
      <!-- tail -->
      <path d="M26 74 L8 84 L14 70 L6 62 L28 64 Z" :fill="c.dark" />
      <!-- body -->
      <g class="body">
        <ellipse cx="58" cy="68" rx="34" ry="28" :fill="c.body" />
        <ellipse cx="66" cy="76" rx="22" ry="18" :fill="c.belly" />
        <path v-if="outfit === 'outfit_hoodie'" d="M28 66 Q58 52 90 66 L90 84 Q58 100 28 84 Z" fill="#5b7bbf" opacity=".95" />
        <path v-if="outfit === 'outfit_hoodie'" d="M50 70 h18" stroke="#3c5aa0" stroke-width="3" stroke-linecap="round" />
        <path v-if="outfit === 'outfit_cape'" d="M30 60 Q24 84 34 96 L52 90 Q40 76 44 60 Z" fill="#8b2f3c" />
      </g>
      <!-- wing -->
      <path class="wing" d="M36 62 Q52 54 66 66 Q56 84 34 80 Q30 70 36 62 Z" :fill="c.dark" />
      <!-- head -->
      <g class="head">
        <circle cx="74" cy="42" r="22" :fill="c.body" />
        <ellipse cx="80" cy="50" rx="13" ry="10" :fill="c.belly" />
        <circle cx="82" cy="51" r="4" :fill="c.cheek" opacity=".7" />
        <g class="eye"><circle cx="80" cy="39" r="5.2" fill="#1b2a4e" /><circle cx="81.6" cy="37.4" r="1.6" fill="#fff" /></g>
        <path v-if="mood === 'sad'" d="M73 31 l9 3" stroke="#1b2a4e" stroke-width="2" stroke-linecap="round" />
        <path d="M94 41 L106 45 L94 49 Z" fill="#e0703c" />
        <!-- accessories -->
        <g v-if="acc === 'crown_small'"><path d="M64 22 L68 12 L74 19 L80 10 L84 21 Z" fill="#f0b53c" stroke="#b5821c" stroke-width="1.5" /></g>
        <g v-if="acc === 'crown_royal'">
          <path d="M58 24 L62 8 L70 18 L76 4 L82 18 L90 8 L92 24 Z" fill="#f0b53c" stroke="#b5821c" stroke-width="1.5" />
          <circle cx="76" cy="16" r="2.5" fill="#c0392b" /><circle cx="65" cy="19" r="1.8" fill="#2e86de" /><circle cx="87" cy="19" r="1.8" fill="#27ae60" />
        </g>
        <g v-if="acc === 'accessory_cap'"><path d="M56 22 L76 12 L96 22 L76 30 Z" fill="#1b2a4e" /><path d="M66 25 v8 q10 5 20 0 v-8" fill="#1b2a4e" /><path d="M96 22 v10" stroke="#f0b53c" stroke-width="2" /></g>
        <g v-if="acc === 'accessory_glasses'" fill="none" stroke="#1b2a4e" stroke-width="2.2"><circle cx="80" cy="39" r="7.5" /><path d="M72.5 38 L62 35" /></g>
        <g v-if="acc === 'accessory_scarf'"><path d="M56 56 Q74 66 92 56 L92 62 Q74 72 56 62 Z" fill="#9b59b6" /><path d="M60 62 l-4 14 l7 -2 z" fill="#8e44ad" /></g>
      </g>
      <!-- feet -->
      <path d="M52 94 v8 M48 102 h8 M66 94 v8 M62 102 h8" stroke="#c97a3c" stroke-width="3" stroke-linecap="round" />
    </g>
    <g v-if="sparkles" class="sparkles" fill="#f0b53c">
      <path d="M18 24 l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2z" /><path d="M100 70 l1.5 4 4 1.5 -4 1.5 -1.5 4 -1.5 -4 -4 -1.5 4 -1.5z" /><path d="M24 96 l1.2 3 3 1.2 -3 1.2 -1.2 3 -1.2 -3 -3 -1.2 3 -1.2z" />
    </g>
    <g v-if="mood === 'thinking'" class="dots" fill="var(--ink-2)"><circle cx="100" cy="18" r="3" /><circle cx="110" cy="12" r="2.2" /><circle cx="116" cy="6" r="1.6" /></g>
    <circle v-if="mood === 'notify'" cx="104" cy="22" r="5" fill="#c0392b" class="ping" />
  </svg>
</template>

<style scoped>
.bird { overflow: visible; flex: none; }
.whole, .body, .head, .wing, .eye { transform-box: fill-box; transform-origin: center; }
.m-idle .body { animation: breathe 3.2s ease-in-out infinite; }
.m-idle .eye { animation: blink 5s infinite; }
.m-idle .head { animation: tilt 7s ease-in-out infinite; }
.m-happy .whole, .m-achievement .whole { animation: hop .7s ease-out 2; }
.m-happy .wing, .m-achievement .wing { transform-origin: 30% 30%; animation: flap .25s ease-in-out 6; }
.m-sad .head { transform: translateY(4px) rotate(8deg); }
.m-sad .whole { animation: shake .4s ease-in-out 1; }
.m-thinking .head { transform: rotate(-8deg); }
.m-thinking .dots circle { animation: fade 1.2s ease-in-out infinite; }
.m-notify .head { animation: lookup .6s ease-out 1 forwards; }
.sparkles { animation: twinkle 1.4s ease-in-out infinite; }
.ping { animation: fade 1s ease-in-out infinite; }
@keyframes breathe { 50% { transform: scale(1.025, 1.04); } }
@keyframes blink { 0%, 92%, 100% { transform: scaleY(1); } 95% { transform: scaleY(.1); } }
@keyframes tilt { 0%, 80%, 100% { transform: rotate(0); } 88% { transform: rotate(-7deg); } }
@keyframes hop { 30% { transform: translateY(-10px); } 60% { transform: translateY(0); } }
@keyframes flap { 50% { transform: rotate(-22deg); } }
@keyframes shake { 25% { transform: translateX(-3px); } 75% { transform: translateX(3px); } }
@keyframes fade { 50% { opacity: .25; } }
@keyframes twinkle { 50% { opacity: .35; transform: scale(.9); } }
@keyframes lookup { to { transform: translateY(-3px) rotate(-10deg); } }
@media (prefers-reduced-motion: reduce) { .bird * { animation: none !important; } }
</style>
