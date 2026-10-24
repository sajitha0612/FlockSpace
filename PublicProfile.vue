<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import Bird from '../components/Bird.vue'
import Nest from '../components/Nest.vue'
import Modal from '../components/Modal.vue'
import StateBlock from '../components/StateBlock.vue'
import { api } from '../lib/api'
import { ago } from '../lib/time'
import { useAction, useLoad } from '../lib/useLoad'
import { useSession } from '../stores/session'

const props = defineProps({ id: { type: String, required: true } })
const session = useSession()
const router = useRouter()
const { busy, run } = useAction(session)
const { data: u, loading, error, reload } = useLoad(() => api.get(`/users/${props.id}`))
const reporting = ref(false)
const rep = reactive({ category: 'harassment', details: '', also_block: false })
const STATE = { studying: ['leaf', 'Studying now'], break: ['gold', 'Taking a break'], available: ['primary', 'Available'], offline: ['', 'Offline'] }
const pretty = (s) => s.replace(/_/g, ' ')
const ord = (n) => (n ? `${n}${['th', 'st', 'nd', 'rd'][(n % 100 > 10 && n % 100 < 14) ? 0 : n % 10 < 4 ? n % 10 : 0]}` : '–')

async function act(fn, msg) { await run(fn, msg); reload() }
async function block() {
  if (!confirm(`Block ${u.value.name}? You'll stop seeing each other's messages, profiles and activity, and follows and buddy links between you are removed.`)) return
  await run(() => api.post(`/users/${props.id}/block`), 'Blocked.')
  router.push('/buddies')
}
async function report() {
  await run(() => api.post('/reports', { target_type: 'user', target_id: props.id, ...rep }), 'Report sent to reviewers.')
  reporting.value = false
  if (rep.also_block) router.push('/buddies')
}
</script>

<template>
  <div class="page">
    <StateBlock :loading="loading" :error="error" :has-data="!!u" @retry="reload">
      <template v-if="u">
        <section class="card head">
          <Bird :bird="u.bird" :size="110" framed :label="`${u.name}'s bird`" />
          <div class="grow">
            <h1>{{ u.name }}</h1>
            <p class="muted">{{ u.year ? `Year ${u.year}` : '' }}<template v-if="u.subjects.length"> · {{ u.subjects.join(', ') }}</template></p>
            <p v-if="u.bio">{{ u.bio }}</p>
            <div class="row small">
              <span>{{ u.followers }} followers</span><span>{{ u.following }} following</span>
              <span v-if="u.relationship.follows_you" class="chip">Follows you</span>
              <span v-if="u.relationship.buddies" class="chip leaf">Buddies</span>
              <span v-if="u.activity" class="chip" :class="STATE[u.activity.state][0]">{{ STATE[u.activity.state][1] }}<template v-if="u.activity.room"> · {{ u.activity.room.title }}</template></span>
            </div>
          </div>
          <div class="stack acts">
            <button v-if="!u.relationship.following" class="btn sm" :disabled="busy" @click="act(() => api.post(`/users/${id}/follow`), 'Following!')">Follow</button>
            <button v-else class="btn secondary sm" :disabled="busy" @click="act(() => api.del(`/users/${id}/follow`), 'Unfollowed.')">Unfollow</button>
            <button v-if="!u.relationship.buddies && !u.relationship.request_sent && !u.relationship.request_received" class="btn secondary sm" :disabled="busy" @click="act(() => api.post(`/users/${id}/buddy-request`), 'Request sent.')">Buddy request</button>
            <RouterLink v-else-if="u.relationship.request_received" to="/buddies?tab=requests" class="btn secondary sm">Answer request</RouterLink>
            <span v-else-if="u.relationship.request_sent" class="chip">Request pending</span>
            <button class="btn ghost sm" @click="reporting = true">Report</button>
            <button class="btn ghost sm" @click="block">Block</button>
          </div>
        </section>

        <div class="grid grid-3">
          <section class="card">
            <h3>Golden Nests</h3>
            <div class="row"><Nest :progress="100" skin="nest_golden" :size="80" label="" /><strong class="big">{{ u.golden_nests }}</strong></div>
          </section>
          <section class="card">
            <h3>Study style</h3>
            <ul class="small plain">
              <li v-if="u.study_style.learning_mode">{{ u.study_style.learning_mode }} learner</li>
              <li v-if="u.study_style.focus_minutes">Focuses ~{{ u.study_style.focus_minutes }} min</li>
              <li v-if="u.study_style.communication">{{ u.study_style.communication }}</li>
              <li v-if="u.study_style.session_type">Prefers: {{ u.study_style.session_type }}</li>
            </ul>
            <div class="row"><span v-for="g in u.goals" :key="g" class="chip">{{ pretty(g) }}</span></div>
          </section>
          <section v-if="u.match" class="card">
            <h3>Your match: {{ Math.round(u.match.score) }}%</h3>
            <ul class="small plain"><li v-for="r in u.match.reasons" :key="r">{{ r }}</li></ul>
            <p v-if="!u.match.reasons.length" class="small muted">No strong overlaps found yet.</p>
          </section>
        </div>
        <section class="card">
          <h3>Recent Nest Races</h3>
          <div v-if="!u.races.length" class="empty small">No races yet.</div>
          <table v-else class="table">
            <thead><tr><th>Room</th><th>Result</th><th>When</th></tr></thead>
            <tbody><tr v-for="(r, i) in u.races" :key="i"><td>{{ r.room }}</td><td>{{ r.status === 'void' ? 'No race' : r.placement ? `${ord(r.placement)} of ${r.eligible_count}` : 'Unranked' }}</td><td>{{ ago(r.finished_at) }}</td></tr></tbody>
          </table>
        </section>
      </template>
    </StateBlock>
    <Modal v-if="reporting" :title="`Report ${u?.name}`" @close="reporting = false">
      <form class="stack" @submit.prevent="report">
        <label class="field">Reason<select v-model="rep.category" class="input"><option value="harassment">Harassment or bullying</option><option value="spam">Spam</option><option value="cheating">Cheating or reward farming</option><option value="inappropriate">Inappropriate</option><option value="privacy">Privacy</option><option value="other">Other</option></select></label>
        <label class="field">What happened?<textarea v-model="rep.details" class="input" maxlength="2000" /></label>
        <label class="check"><input v-model="rep.also_block" type="checkbox" /> Also block them</label>
        <p class="small muted">Reviewers handle reports confidentially; they won't be told who reported them.</p>
        <button class="btn danger" :disabled="busy">Send report</button>
      </form>
    </Modal>
  </div>
</template>

<style scoped>
.head { display: flex; gap: 18px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
.head h1 { margin: 0; }
.grow { flex: 1; min-width: 220px; }
.acts { min-width: 150px; }
.big { font-size: 2.4rem; }
.plain { list-style: none; padding: 0; margin: 0 0 8px; }
.grid { margin-bottom: 16px; }
</style>
