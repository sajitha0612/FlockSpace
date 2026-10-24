<script setup>
import Bird from '../components/Bird.vue'
import Nest from '../components/Nest.vue'
import StateBlock from '../components/StateBlock.vue'
import { api } from '../lib/api'
import { ago } from '../lib/time'
import { useLoad } from '../lib/useLoad'
import { useSession } from '../stores/session'

const session = useSession()
const { data, loading, error, reload } = useLoad(() => api.get('/me/achievements'))
const ord = (n) => (n ? `${n}${['th', 'st', 'nd', 'rd'][(n % 100 > 10 && n % 100 < 14) ? 0 : n % 10 < 4 ? n % 10 : 0]}` : '–')
const ICON = { accessory_scarf: { accessory: 'accessory_scarf' }, crown_royal: { accessory: 'crown_royal' } }
</script>

<template>
  <div class="page">
    <StateBlock :loading="loading" :error="error" :has-data="!!data" @retry="reload">
      <template v-if="data">
        <section class="hero">
          <div class="stars" aria-hidden="true" />
          <div class="hero-art"><Bird :bird="session.user.bird" :size="120" :mood="data.golden_nests ? 'achievement' : 'idle'" label="" /><Nest :progress="100" skin="nest_golden" :size="200" label="" /></div>
          <h1>{{ data.golden_nests }} Golden Nest{{ data.golden_nests === 1 ? '' : 's' }}</h1>
          <p v-if="data.next_milestone">{{ data.next_milestone.remaining }} more to unlock <strong>{{ data.next_milestone.name }}</strong></p>
          <p v-else-if="data.golden_nests">Every milestone unlocked. Legendary!</p>
          <p class="small rule">Golden Nests go to Nest Race winners: the top 3 when more than 5 eligible students race, otherwise 1st place only.</p>
        </section>

        <section class="card">
          <h3>Milestone rewards</h3>
          <div class="miles">
            <div v-for="m in data.milestones" :key="m.at" class="mile" :class="{ done: m.unlocked }">
              <div class="pv">
                <Nest v-if="m.item.startsWith('nest_')" :progress="100" :skin="m.item" :size="80" :label="m.name" />
                <Bird v-else :bird="{ ...session.user.bird, ...(ICON[m.item] || {}) }" :size="64" :label="m.name" />
              </div>
              <strong>{{ m.at }}</strong>
              <span class="small">{{ m.name }}</span>
              <div class="bar gold"><span :style="{ width: (100 * m.progress) / m.at + '%' }" /></div>
              <span class="tiny muted">{{ m.unlocked ? 'Unlocked' : `${m.progress}/${m.at}` }}</span>
            </div>
          </div>
        </section>

        <div class="grid grid-2">
          <section class="card">
            <h3>Golden Nest history</h3>
            <div v-if="!data.history.length" class="empty small">Win a Nest Race to earn your first Golden Nest.</div>
            <div class="list">
              <div v-for="(g, i) in data.history" :key="i" class="item">
                <span class="chip" :class="g.status === 'awarded' ? 'gold' : 'warn'">{{ ord(g.placement) }}</span>
                <RouterLink :to="`/rooms/${g.room_id}?tab=race`" class="grow">{{ g.room }}</RouterLink>
                <span class="small muted">{{ g.status === 'withheld' ? 'Pending review' : ago(g.awarded_at) }}</span>
              </div>
            </div>
          </section>
          <section class="card">
            <h3>All race placements</h3>
            <div v-if="!data.races.length" class="empty small">No races yet.</div>
            <table v-else class="table">
              <thead><tr><th>Room</th><th>Place</th><th class="num">Twigs</th><th class="num">Accuracy</th></tr></thead>
              <tbody><tr v-for="r in data.races" :key="r.race_id"><td>{{ r.room }}</td><td>{{ r.status === 'void' ? 'No race' : r.placement ? `${ord(r.placement)} / ${r.eligible_count}` : 'Unranked' }}</td><td class="num">{{ r.twigs }}</td><td class="num">{{ r.accuracy }}%</td></tr></tbody>
            </table>
          </section>
        </div>
      </template>
    </StateBlock>
  </div>
</template>

<style scoped>
.hero { position: relative; overflow: hidden; border-radius: var(--radius); padding: 28px 20px; text-align: center; color: #fff; background: radial-gradient(circle at 50% 35%, #4a3f8a 0%, #241f4d 60%, #171433 100%); margin-bottom: 16px; }
.hero h1 { color: #fff; margin-top: 8px; }
.hero p { color: #e5e1ff; }
.rule { opacity: .8; }
.hero-art { display: flex; flex-direction: column; align-items: center; }
.hero-art :deep(svg:first-child) { margin-bottom: -60px; position: relative; z-index: 1; }
.stars { position: absolute; inset: 0; background-image: radial-gradient(2px 2px at 20% 30%, #f3c95a, transparent), radial-gradient(2px 2px at 80% 20%, #fff, transparent), radial-gradient(1.5px 1.5px at 65% 70%, #f3c95a, transparent), radial-gradient(1.5px 1.5px at 30% 80%, #fff, transparent), radial-gradient(2px 2px at 90% 60%, #9ec5f4, transparent); opacity: .8; }
.miles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-top: 10px; }
.mile { border: 1px solid var(--border); border-radius: 14px; padding: 12px; display: flex; flex-direction: column; align-items: center; gap: 4px; text-align: center; }
.mile.done { border-color: var(--gold); background: var(--gold-soft); }
.mile strong { font-size: 1.3rem; }
.mile .bar { width: 100%; }
.pv { height: 72px; display: grid; place-items: center; }
.grid { margin-top: 16px; }
.grow { flex: 1; }
</style>
