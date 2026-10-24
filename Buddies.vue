<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Bird from '../components/Bird.vue'
import StateBlock from '../components/StateBlock.vue'
import { api } from '../lib/api'
import { useAction, useLoad } from '../lib/useLoad'
import { useSession } from '../stores/session'

const session = useSession()
const route = useRoute()
const router = useRouter()
const { busy, run } = useAction(session)
const tab = computed({ get: () => route.query.tab || 'find', set: (v) => router.replace({ query: { tab: v } }) })
const recs = useLoad(() => api.get('/buddies/recommendations'))
const conns = useLoad(() => api.get('/me/connections'))
const reqs = useLoad(() => api.get('/me/buddy-requests'))
const now = useLoad(() => api.get('/buddies/studying-now'))
const nudges = useLoad(() => api.get('/nudges/messages'))
const open = ref(null)
const CRIT = { C: 'Common subjects', T: 'Study times', G: 'Study goals', A: 'Academic year', P: 'Study style' }

async function act(fn, msg) {
  await run(fn, msg)
  recs.reload(); conns.reload(); reqs.reload()
}
const follow = (u) => act(() => api.post(`/users/${u.user_id || u.id}/follow`), `Following ${u.name}`)
const unfollow = (u) => act(() => api.del(`/users/${u.id}/follow`), 'Unfollowed.')
const request = (u) => act(() => api.post(`/users/${u.user_id || u.id}/buddy-request`), 'Buddy request sent.')
const respond = (r, action) => act(() => api.post(`/buddy-requests/${r.id}`, { action }), { accept: 'You’re buddies now!', reject: 'Request declined.', cancel: 'Request cancelled.' }[action])
const unbuddy = (u) => confirm(`Remove ${u.name} as a buddy?`) && act(() => api.del(`/users/${u.id}/buddy`), 'Buddy removed.')
async function nudge(u, key) {
  await run(() => api.post(`/users/${u.id}/nudge`, { message: key }), `Nudge sent to ${u.name}.`)
}
// so cards in "Find buddies" show what's already been done instead of offering the same action twice
const followingIds = computed(() => new Set((conns.data.value?.following || []).map((u) => u.id)))
const buddyIds = computed(() => new Set((conns.data.value?.buddies || []).map((u) => u.id)))
const sentIds = computed(() => new Set((reqs.data.value?.outgoing || []).map((r) => r.user.id)))
const receivedIds = computed(() => new Set((reqs.data.value?.incoming || []).map((r) => r.user.id)))
const STATE = { studying: ['leaf', 'Studying now'], break: ['gold', 'Taking a break'], available: ['primary', 'Available'], offline: ['', 'Offline'] }
</script>

<template>
  <div class="page">
    <div class="page-head"><div><h1>Study buddies</h1><p>Following is one-way. Buddies are mutual and need a request.</p></div></div>
    <div class="tabs" role="tablist">
      <button v-for="t in [['find', 'Find buddies'], ['now', 'Studying now'], ['connections', 'Following & buddies'], ['requests', 'Requests']]" :key="t[0]" :class="{ on: tab === t[0] }" role="tab" :aria-selected="tab === t[0]" @click="tab = t[0]">
        {{ t[1] }}<span v-if="t[0] === 'requests' && reqs.data.value?.incoming.length" class="chip danger count">{{ reqs.data.value.incoming.length }}</span>
      </button>
    </div>

    <div class="body">
      <StateBlock v-if="tab === 'find'" :loading="recs.loading.value" :error="recs.error.value" :has-data="!!recs.data.value" @retry="recs.reload">
        <template v-if="recs.data.value">
          <p v-if="!recs.data.value.profile_complete" class="notice warn">Add your subjects and answer the study-style questions in <RouterLink to="/settings">Settings</RouterLink> for better matches.</p>
          <div v-if="!recs.data.value.recommendations.length" class="empty">No one to suggest yet. Invite classmates to join FlockSpace!</div>
          <div class="grid grid-2">
            <article v-for="r in recs.data.value.recommendations" :key="r.user_id" class="card rec">
              <div class="row top">
                <Bird :bird="r.bird" :size="54" framed label="" />
                <div class="grow">
                  <RouterLink :to="`/u/${r.user_id}`" class="name">{{ r.name }}</RouterLink>
                  <div class="small muted">{{ r.year ? `Year ${r.year}` : 'Year not set' }}<template v-if="r.subjects.length"> · {{ r.subjects.join(', ') }}</template></div>
                </div>
                <div class="score"><strong>{{ r.score }}%</strong><span class="tiny muted">match</span></div>
              </div>
              <ul v-if="r.reasons.length" class="reasons small"><li v-for="x in r.reasons" :key="x">{{ x }}</li></ul>
              <p v-else class="small muted">No strong shared signals yet.</p>
              <button class="btn ghost sm" :aria-expanded="open === r.user_id" @click="open = open === r.user_id ? null : r.user_id">{{ open === r.user_id ? 'Hide' : 'How is this calculated?' }}</button>
              <div v-if="open === r.user_id" class="breakdown small">
                <div v-for="(v, k) in r.breakdown" :key="k" class="crit">
                  <span>{{ CRIT[k] }}</span>
                  <div class="bar"><span :style="{ width: v.value * 100 + '%' }" /></div>
                  <span class="mono">{{ v.points }}/{{ v.weight }}</span>
                </div>
                <p class="tiny muted">Profile score {{ r.profile_score }} = 40×subjects + 25×times + 15×goals + 10×year + 10×style.
                  <template v-if="r.bayes.evidence">Past sessions and feedback ({{ r.bayes.evidence }} pieces of evidence) adjust it by {{ r.bayes.adjustment > 0 ? '+' : '' }}{{ r.bayes.adjustment }}.</template>
                  <template v-else>No shared sessions yet, so no adjustment.</template>
                  <template v-if="r.missing.length"> Missing info: {{ r.missing.join(', ') }}.</template>
                </p>
              </div>
              <div class="row">
                <button v-if="followingIds.has(r.user_id)" class="btn ghost sm" :disabled="busy" @click="unfollow({ id: r.user_id })">Following ✓</button>
                <button v-else class="btn sm" :disabled="busy" @click="follow(r)">Follow</button>
                <span v-if="buddyIds.has(r.user_id)" class="chip leaf">Buddies</span>
                <button v-else-if="sentIds.has(r.user_id)" class="btn ghost sm" disabled>Request sent</button>
                <button v-else-if="receivedIds.has(r.user_id)" class="btn secondary sm" @click="tab = 'requests'">Respond to request</button>
                <button v-else class="btn secondary sm" :disabled="busy" @click="request(r)">Buddy request</button>
              </div>
            </article>
          </div>
        </template>
      </StateBlock>

      <StateBlock v-if="tab === 'now'" :loading="now.loading.value" :error="now.error.value" :has-data="!!now.data.value" :empty="now.data.value && !now.data.value.length" empty-text="None of the people you follow are online right now (or they keep their status private)." @retry="now.reload">
        <div class="card list">
          <div v-for="u in now.data.value" :key="u.id" class="item">
            <Bird :bird="u.bird" :size="44" framed :mood="u.activity.state === 'studying' ? 'idle' : 'notify'" label="" />
            <div class="grow">
              <RouterLink :to="`/u/${u.id}`" class="name">{{ u.name }}</RouterLink>
              <div class="small muted"><template v-if="u.activity.room">in <RouterLink :to="`/rooms/${u.activity.room.id}`">{{ u.activity.room.title }}</RouterLink></template></div>
            </div>
            <span class="chip" :class="STATE[u.activity.state][0]">{{ STATE[u.activity.state][1] }}</span>
          </div>
        </div>
      </StateBlock>

      <StateBlock v-if="tab === 'connections'" :loading="conns.loading.value" :error="conns.error.value" :has-data="!!conns.data.value" @retry="conns.reload">
        <div v-if="conns.data.value" class="grid grid-3">
          <section v-for="[key, label] in [['buddies', 'Buddies'], ['following', 'Following'], ['followers', 'Followers']]" :key="key" class="card">
            <h3>{{ label }} ({{ conns.data.value[key].length }})</h3>
            <div v-if="!conns.data.value[key].length" class="empty small">None yet.</div>
            <div class="list">
              <div v-for="u in conns.data.value[key]" :key="u.id" class="item">
                <Bird :bird="u.bird" :size="36" framed label="" />
                <div class="grow">
                  <RouterLink :to="`/u/${u.id}`" class="name">{{ u.name }}</RouterLink>
                  <div v-if="u.activity" class="tiny"><span class="chip" :class="STATE[u.activity.state][0]">{{ STATE[u.activity.state][1] }}</span></div>
                </div>
                <details v-if="key !== 'following'" class="nudge">
                  <summary class="btn ghost sm">Nudge</summary>
                  <div class="menu card"><button v-for="(text, k) in nudges.data.value || {}" :key="k" class="btn ghost sm" :disabled="busy" @click="nudge(u, k)">{{ text }}</button></div>
                </details>
                <button v-if="key === 'following'" class="btn ghost sm" :disabled="busy" @click="unfollow(u)">Unfollow</button>
                <button v-if="key === 'buddies'" class="btn ghost sm" :disabled="busy" @click="unbuddy(u)">Remove</button>
              </div>
            </div>
          </section>
        </div>
      </StateBlock>

      <StateBlock v-if="tab === 'requests'" :loading="reqs.loading.value" :error="reqs.error.value" :has-data="!!reqs.data.value" @retry="reqs.reload">
        <div v-if="reqs.data.value" class="grid grid-2">
          <section class="card">
            <h3>Incoming</h3>
            <div v-if="!reqs.data.value.incoming.length" class="empty small">No requests.</div>
            <div class="list">
              <div v-for="r in reqs.data.value.incoming" :key="r.id" class="item">
                <Bird :bird="r.user.bird" :size="36" framed label="" />
                <RouterLink :to="`/u/${r.user.id}`" class="grow name">{{ r.user.name }}</RouterLink>
                <button class="btn sm" :disabled="busy" @click="respond(r, 'accept')">Accept</button>
                <button class="btn ghost sm" :disabled="busy" @click="respond(r, 'reject')">Decline</button>
              </div>
            </div>
          </section>
          <section class="card">
            <h3>Sent</h3>
            <div v-if="!reqs.data.value.outgoing.length" class="empty small">No pending requests.</div>
            <div class="list">
              <div v-for="r in reqs.data.value.outgoing" :key="r.id" class="item">
                <span class="grow">{{ r.user.name }}</span>
                <button class="btn ghost sm" :disabled="busy" @click="respond(r, 'cancel')">Cancel</button>
              </div>
            </div>
          </section>
        </div>
      </StateBlock>
    </div>
  </div>
</template>

<style scoped>
.body { margin-top: 16px; }
.rec { display: flex; flex-direction: column; gap: 8px; }
.top { flex-wrap: nowrap; }
.grow { flex: 1; min-width: 0; }
.name { font-weight: 800; color: var(--ink); }
.score { display: flex; flex-direction: column; align-items: center; background: var(--leaf-soft); color: var(--leaf); border-radius: 12px; padding: 4px 10px; }
.score strong { font-size: 1.3rem; }
.reasons { margin: 0; padding-left: 18px; color: var(--ink-2); }
.breakdown { background: var(--surface-2); border-radius: 10px; padding: 10px; }
.crit { display: grid; grid-template-columns: 120px 1fr 50px; gap: 8px; align-items: center; margin: 4px 0; }
.nudge { position: relative; }
.nudge summary { list-style: none; }
.nudge .menu { position: absolute; right: 0; z-index: 5; display: flex; flex-direction: column; padding: 6px; min-width: 240px; }
.nudge .menu .btn { justify-content: flex-start; }
</style>
