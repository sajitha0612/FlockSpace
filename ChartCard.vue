<script setup>
// Frame for every chart: title, optional legend (shown for 2+ series), and a table view of the same rows.
import { ref } from 'vue'
import Icon from '../Icon.vue'

defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  legend: { type: Array, default: () => [] }, // [{label, color}]
  columns: { type: Array, default: () => [] }, // [{key, label, num}]
  rows: { type: Array, default: () => [] },
  empty: Boolean,
  emptyText: { type: String, default: 'No activity in this period yet.' },
})
const table = ref(false)
</script>

<template>
  <section class="card chart-card">
    <div class="row-between">
      <div>
        <h3>{{ title }}</h3>
        <p v-if="subtitle" class="muted small sub">{{ subtitle }}</p>
      </div>
      <button v-if="columns.length && !empty" class="btn ghost sm" :aria-pressed="table" @click="table = !table">
        <Icon name="table" :size="16" /> {{ table ? 'Chart' : 'Table' }}
      </button>
    </div>
    <div v-if="legend.length > 1 && !table" class="legend">
      <span v-for="l in legend" :key="l.label" class="key"><span class="sw" :style="{ background: l.color }" />{{ l.label }}</span>
    </div>
    <div v-if="empty" class="empty small">{{ emptyText }}</div>
    <div v-else-if="table" class="table-wrap">
      <table class="table">
        <thead><tr><th v-for="c in columns" :key="c.key" :class="{ num: c.num }">{{ c.label }}</th></tr></thead>
        <tbody><tr v-for="(r, i) in rows" :key="i"><td v-for="c in columns" :key="c.key" :class="{ num: c.num }">{{ r[c.key] }}</td></tr></tbody>
      </table>
    </div>
    <slot v-else />
  </section>
</template>

<style scoped>
.chart-card h3 { margin: 0; }
.chart-card > .row-between { flex-wrap: nowrap; align-items: flex-start; }
.sub { margin: 2px 0 0; }
.legend { display: flex; flex-wrap: wrap; gap: 14px; margin: 10px 0 2px; font-size: .82rem; color: var(--ink-2); font-weight: 600; }
.key { display: inline-flex; align-items: center; gap: 6px; }
.sw { width: 12px; height: 12px; border-radius: 3px; }
.table-wrap { max-height: 280px; overflow: auto; margin-top: 8px; }
</style>
