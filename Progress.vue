<script setup>
import { computed, ref, watch } from 'vue'
import StateBlock from '../components/StateBlock.vue'
import ChartCard from '../components/charts/ChartCard.vue'
import BarChart from '../components/charts/BarChart.vue'
import LineChart from '../components/charts/LineChart.vue'
import Heatmap from '../components/charts/Heatmap.vue'
import { api } from '../lib/api'
import { useLoad } from '../lib/useLoad'
import { withExampleAnalytics, withExampleStreak } from '../lib/exampleData'

const range = ref('week')
const { data, loading, error, reload } = useLoad(async () => withExampleAnalytics(await api.get(`/me/analytics?range=${range.value}`)))
const streak = useLoad(async () => withExampleStreak(await api.get('/me/streak')))
watch(range, reload)

const fmtKey = (k) => {
  const d = new Date(k + 'T00:00:00')
  return data.value?.bucket === 'week' ? `wk ${d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}` : range.value === 'week' ? d.toLocaleDateString(undefined, { weekday: 'short' }) : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}
const s = computed(() => data.value?.series || [])
const hasStudy = computed(() => s.value.some((x) => x.minutes || x.completed || x.interrupted))
const quizPoints = computed(() => (data.value?.quiz || []).map((q) => ({ label: new Date(q.date + 'T00:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'short' }), value: q.accuracy, note: q.kind === 'race' ? 'Nest Race' : 'Halfway quiz' })))
const maxSubject = computed(() => Math.max(1, ...(data.value?.subjects || []).map((x) => x.minutes)))
const pvc = computed(() => data.value?.planned_vs_completed)
const meters = computed(() => pvc.value ? [
  { label: 'Topics in your rooms', ...pvc.value.topics },
  { label: 'Shared tasks', ...pvc.value.tasks },
  { label: 'Days goal met', ...pvc.value.goal_days },
] : [])
const ord = (n) => (n ? `${n}${['th', 'st', 'nd', 'rd'][(n % 100 > 10 && n % 100 < 14) ? 0 : n % 10 < 4 ? n % 10 : 0]}` : '–')
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div><h1>Your progress</h1><p>Only completed focus sessions count as study time. Interrupted ones are shown separately.</p></div>
      <div class="segmented" role="group" aria-label="Time range">
        <button v-for="r in [['week', 'Week'], ['month', 'Month'], ['all', 'All time']]" :key="r[0]" :class="{ on: range === r[0] }" :aria-pressed="range === r[0]" @click="range = r[0]">{{ r[1] }}</button>
      </div>
    </div>

    <StateBlock :loading="loading" :error="error" :has-data="!!data" @retry="reload">
      <template v-if="data">
        <p v-if="data.example" class="notice info small example">Example data: this is what your charts will look like. Complete a focus session in a room and your own numbers replace it.</p>
        <div class="grid grid-4 tiles">
          <div class="card tile"><span class="muted small">Focus time</span><strong>{{ Math.floor(data.totals.minutes / 60) }}h {{ data.totals.minutes % 60 }}m</strong></div>
          <div class="card tile"><span class="muted small">Completed sessions</span><strong>{{ data.totals.completed_sessions }}</strong><span class="tiny muted">{{ data.totals.interrupted_sessions }} stopped early</span></div>
          <div class="card tile"><span class="muted small">Topics completed</span><strong>{{ data.totals.topics }}</strong></div>
          <div class="card tile"><span class="muted small">Twigs earned</span><strong>{{ data.totals.twigs }}</strong></div>
        </div>

        <div class="grid grid-2">
          <ChartCard title="Daily focus time" :subtitle="`Minutes of completed focus per ${data.bucket}, against your ${data.goal_minutes}-minute daily goal`"
                     :columns="[{ key: 'k', label: 'Period' }, { key: 'minutes', label: 'Minutes', num: true }]" :rows="s.map((x) => ({ k: fmtKey(x.key), minutes: x.minutes }))" :empty="!hasStudy">
            <BarChart :rows="s.map((x) => ({ label: x.key, minutes: x.minutes }))" :series="[{ key: 'minutes', label: 'Minutes', color: 'var(--series-1)' }]"
                      :ref-line="data.bucket === 'day' ? { value: data.goal_minutes, label: `Goal ${data.goal_minutes}` } : null" :label-format="fmtKey" />
          </ChartCard>
          <ChartCard title="Sessions" subtitle="Completed focus sessions vs ones stopped early or too short to count"
                     :legend="[{ label: 'Completed', color: 'var(--series-1)' }, { label: 'Stopped early / short', color: 'var(--series-2)' }]"
                     :columns="[{ key: 'k', label: 'Period' }, { key: 'c', label: 'Completed', num: true }, { key: 'i', label: 'Stopped early', num: true }]"
                     :rows="s.map((x) => ({ k: fmtKey(x.key), c: x.completed, i: x.interrupted }))" :empty="!hasStudy">
            <BarChart :rows="s.map((x) => ({ label: x.key, completed: x.completed, interrupted: x.interrupted }))"
                      :series="[{ key: 'completed', label: 'Completed', color: 'var(--series-1)' }, { key: 'interrupted', label: 'Stopped early', color: 'var(--series-2)' }]" :label-format="fmtKey" />
          </ChartCard>
          <ChartCard title="Topics completed" subtitle="Topics you ticked off in your rooms (your own declaration of progress)"
                     :columns="[{ key: 'k', label: 'Period' }, { key: 't', label: 'Topics', num: true }]" :rows="s.map((x) => ({ k: fmtKey(x.key), t: x.topics }))" :empty="!s.some((x) => x.topics)">
            <BarChart :rows="s.map((x) => ({ label: x.key, topics: x.topics }))" :series="[{ key: 'topics', label: 'Topics', color: 'var(--series-3)' }]" :label-format="fmtKey" />
          </ChartCard>
          <ChartCard title="Quiz accuracy" subtitle="Halfway quizzes and Nest Races, in order"
                     :columns="[{ key: 'label', label: 'Date' }, { key: 'note', label: 'Quiz' }, { key: 'value', label: 'Accuracy %', num: true }]" :rows="quizPoints" :empty="!quizPoints.length" empty-text="No quizzes in this period.">
            <LineChart :points="quizPoints" />
          </ChartCard>
          <ChartCard title="Twigs earned" subtitle="From quizzes and race placements only"
                     :columns="[{ key: 'k', label: 'Period' }, { key: 't', label: 'Twigs', num: true }]" :rows="s.map((x) => ({ k: fmtKey(x.key), t: x.twigs }))" :empty="!s.some((x) => x.twigs)">
            <BarChart :rows="s.map((x) => ({ label: x.key, twigs: x.twigs }))" :series="[{ key: 'twigs', label: 'Twigs', color: 'var(--series-1)' }]" :label-format="fmtKey" />
          </ChartCard>
          <ChartCard title="Weekly consistency" subtitle="Days you met your goal in each of the last 8 weeks"
                     :columns="[{ key: 'week', label: 'Week of' }, { key: 'days_met', label: 'Days met', num: true }, { key: 'days', label: 'Days', num: true }]" :rows="data.consistency">
            <BarChart :rows="data.consistency.map((c) => ({ label: c.week, met: c.days_met }))" :series="[{ key: 'met', label: 'Days goal met', color: 'var(--series-3)' }]"
                      :label-format="(k) => new Date(k + 'T00:00:00').toLocaleDateString(undefined, { day: 'numeric', month: 'short' })" />
          </ChartCard>

          <section class="card">
            <h3>Study time by subject</h3>
            <div v-if="!data.subjects.length" class="empty small">No completed sessions in this period.</div>
            <div v-for="x in data.subjects" :key="x.subject" class="hbar">
              <span class="name">{{ x.subject }}</span>
              <div class="track"><span :style="{ width: (100 * x.minutes) / maxSubject + '%' }" /></div>
              <span class="val mono">{{ x.minutes }} min</span>
            </div>
          </section>

          <section class="card">
            <h3>Planned vs completed</h3>
            <div v-for="m in meters" :key="m.label" class="meter">
              <div class="row-between small"><span>{{ m.label }}</span><span class="mono">{{ m.completed }} / {{ m.planned }}</span></div>
              <div class="bar leaf"><span :style="{ width: m.planned ? (100 * m.completed) / m.planned + '%' : '0%' }" /></div>
            </div>
          </section>

          <section class="card">
            <h3>Nest Race placements</h3>
            <div v-if="!data.placements.length" class="empty small">No races in this period.</div>
            <table v-else class="table">
              <thead><tr><th>Date</th><th>Room</th><th class="num">Place</th></tr></thead>
              <tbody><tr v-for="(p, i) in data.placements" :key="i"><td>{{ p.date }}</td><td>{{ p.room }}</td><td class="num">{{ p.status === 'void' ? 'No race' : p.placement ? `${ord(p.placement)} of ${p.of}` : 'Unranked' }}</td></tr></tbody>
            </table>
          </section>

          <section class="card">
            <h3>Golden Nests</h3>
            <p class="muted small">{{ data.golden.length }} earned in total.</p>
            <div class="row"><span v-for="(g, i) in data.golden" :key="i" class="chip gold" :title="g.date">#{{ i + 1 }} · {{ ord(g.placement) }}</span></div>
            <RouterLink to="/achievements" class="small">See milestones</RouterLink>
          </section>
        </div>
      </template>
    </StateBlock>

    <section v-if="streak.data.value" class="card streak-card">
      <div class="row-between"><h3>Streak: {{ streak.data.value.current }} day{{ streak.data.value.current === 1 ? '' : 's' }}</h3><span class="muted small">Longest {{ streak.data.value.longest }} · timezone {{ streak.data.value.timezone }}</span></div>
      <p v-if="streak.data.value.example && !data?.example" class="small muted">Example calendar until you complete your first focus session.</p>
      <Heatmap :days="streak.data.value.heatmap" :goal="streak.data.value.goal_minutes" />
      <details class="small"><summary>What counts toward a streak?</summary><p class="rule">{{ streak.data.value.rule }}</p></details>
    </section>
  </div>
</template>

<style scoped>
.tiles { margin-bottom: 16px; }
.example { margin-bottom: 14px; }
.tile { display: flex; flex-direction: column; gap: 2px; }
.tile strong { font-size: 1.7rem; line-height: 1.15; }
.hbar { display: grid; grid-template-columns: 120px 1fr 70px; gap: 10px; align-items: center; margin: 8px 0; font-size: .9rem; }
.name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.track { height: 14px; background: var(--surface-3); border-radius: 4px; }
.track span { display: block; height: 100%; background: var(--series-1); border-radius: 0 4px 4px 0; }
.val { text-align: right; color: var(--ink-2); }
.meter { margin: 10px 0; }
.streak-card { margin-top: 16px; }
.rule { white-space: pre-line; color: var(--ink-2); }
</style>
