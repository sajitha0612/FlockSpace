<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ProfileForm from '../components/ProfileForm.vue'
import Questionnaire from '../components/Questionnaire.vue'
import StateBlock from '../components/StateBlock.vue'
import { api, backend } from '../lib/api'
import { resetDemo } from '../lib/demo'
import { ago } from '../lib/time'
import { useAction, useLoad } from '../lib/useLoad'
import { useSession } from '../stores/session'

const session = useSession()
const route = useRoute()
const router = useRouter()
const { busy, run } = useAction(session)
const tab = computed({ get: () => route.query.tab || 'profile', set: (v) => router.replace({ query: { tab: v } }) })
const settings = useLoad(() => api.get('/me/settings'))
const blocked = useLoad(() => api.get('/me/blocked'))
const safety = useLoad(() => api.get('/me/restrictions'))
const reports = useLoad(() => api.get('/me/reports'))
const appealFor = ref(null)
const appealText = ref('')
const permission = ref('Notification' in window ? Notification.permission : 'unsupported')
const NOTIFY = { meeting_reminders: 'Meeting reminders', invites: 'Invitations', buddy: 'Buddy requests & follows', nudges: 'Nudges', race: 'Races & room updates', ai: 'AI requests finished', rewards: 'Rewards & account notices' }

async function save(patch) {
  settings.data.value = await run(() => api.patch('/me/settings', patch), 'Saved.')
}
async function enableBrowser(on) {
  if (on && permission.value === 'default') permission.value = await Notification.requestPermission()
  if (on && permission.value !== 'granted') { session.toast('Your browser blocked notifications for this site.', 'error'); return }
  save({ notify: { browser: on } })
}
async function unblock(u) {
  await run(() => api.del(`/users/${u.id}/block`), `Unblocked ${u.name}.`)
  blocked.reload()
}
async function sendAppeal() {
  await run(() => api.post('/appeals', { restriction_id: appealFor.value.id, text: appealText.value }), 'Appeal sent. A reviewer will respond.')
  appealFor.value = null
  appealText.value = ''
  safety.reload()
}
const s = computed(() => settings.data.value)
const audience = reactive({ everyone: 'Everyone', followers: 'People who follow me & buddies', buddies: 'Buddies only', nobody: 'Nobody' })
function resetDemoData() {
  if (!confirm('Reset the offline demo? Rooms, buddies, meetings and progress go back to the sample data, and you’ll be signed out.')) return
  resetDemo()
  session.signOut()
  router.push('/login')
}
const KIND = { suspended: 'Account suspended', chat_ban: 'Chat restricted', reward_hold: 'Rewards on hold' }
</script>

<template>
  <div class="page">
    <div class="page-head"><div><h1>Settings</h1></div></div>
    <div class="tabs" role="tablist">
      <button v-for="t in [['profile', 'Profile'], ['style', 'Study style'], ['privacy', 'Privacy'], ['notifications', 'Notifications'], ['blocked', 'Blocked'], ['safety', 'Safety & appeals'], ...(backend.demo ? [['demo', 'Demo data']] : [])]" :key="t[0]" :class="{ on: tab === t[0] }" role="tab" @click="tab = t[0]">{{ t[1] }}</button>
    </div>
    <div class="body">
      <section v-if="tab === 'demo'" class="card stack">
        <h3>Offline demo</h3>
        <p class="muted">The FlockSpace server isn’t reachable, so the app is running on sample data stored in this browser. Rooms, chat, the focus timer, buddies, meetings, your profile and progress all work. AI notes, file uploads, quizzes and races need the server.</p>
        <p class="small muted">Start the backend (see the README) and reload to switch back to the real server. Add <code>?demo=1</code> to the address to force the demo, or <code>?demo=0</code> to undo that.</p>
        <div><button class="btn danger sm" @click="resetDemoData">Reset demo data</button></div>
      </section>
      <section v-if="tab === 'profile'" class="card">
        <ProfileForm @saved="session.toast('Profile saved.', 'ok'); session.refreshUser()" />
        <hr />
        <p class="small">Email: {{ session.user.email }} · <span :class="session.user.email_verified ? 'ok' : 'warn'">{{ session.user.email_verified ? 'verified' : 'not verified' }}</span>
          <RouterLink v-if="!session.user.email_verified" to="/verify"> Verify now</RouterLink></p>
        <p class="small"><RouterLink to="/forgot">Change password</RouterLink> (signs out all other sessions)</p>
      </section>
      <section v-if="tab === 'style'" class="card">
        <p class="muted">These 10 questions shape buddy matching. Others see only short labels like "Collaborative learner", never your answers.</p>
        <Questionnaire @saved="session.toast('Study style updated.', 'ok'); session.refreshUser()" />
      </section>

      <StateBlock v-if="tab === 'privacy'" :loading="settings.loading.value" :error="settings.error.value" :has-data="!!s" @retry="settings.reload">
        <section v-if="s" class="card stack">
          <label class="check"><input type="checkbox" :checked="s.discoverable" @change="save({ discoverable: $event.target.checked })" /> Show me in buddy recommendations and search</label>
          <label class="field">Who can see what I'm doing ("Studying now", focus/break status)
            <select class="input" :value="s.activity_visibility" @change="save({ activity_visibility: $event.target.value })"><option v-for="(l, k) in audience" :key="k" :value="k">{{ l }}</option></select>
            <span class="hint">Inside a room, people studying with you see your status unless you choose Nobody. Private room names are never shown.</span>
          </label>
          <label class="field">Who can send me buddy requests
            <select class="input" :value="s.who_can_request" @change="save({ who_can_request: $event.target.value })"><option value="everyone">Everyone</option><option value="nobody">Nobody</option></select>
          </label>
          <label class="field">Who can invite me to rooms and meetings
            <select class="input" :value="s.who_can_invite" @change="save({ who_can_invite: $event.target.value })"><option value="everyone">Everyone</option><option value="followers">People I follow &amp; buddies</option><option value="buddies">Buddies only</option><option value="nobody">Nobody</option></select>
          </label>
          <label class="check"><input type="checkbox" :checked="s.nudges_enabled" @change="save({ nudges_enabled: $event.target.checked })" /> Allow motivational nudges</label>
        </section>
      </StateBlock>

      <StateBlock v-if="tab === 'notifications'" :loading="settings.loading.value" :error="settings.error.value" :has-data="!!s" @retry="settings.reload">
        <section v-if="s" class="card stack">
          <p class="muted small">In-app notifications are always kept in your inbox. System notifications pop up when FlockSpace is open in the background.</p>
          <label class="check"><input type="checkbox" :checked="s.notify.browser" :disabled="permission === 'unsupported' || permission === 'denied'" @change="enableBrowser($event.target.checked)" /> System (browser) notifications</label>
          <p v-if="permission === 'denied'" class="notice warn small">Your browser is blocking notifications for this site. Allow them in the browser's site settings to turn this on.</p>
          <p v-if="permission === 'unsupported'" class="small muted">This browser doesn't support system notifications.</p>
          <fieldset class="box" :disabled="!s.notify.browser">
            <legend>Show system notifications for</legend>
            <label v-for="(l, k) in NOTIFY" :key="k" class="check"><input type="checkbox" :checked="s.notify[k]" @change="save({ notify: { [k]: $event.target.checked } })" /> {{ l }}</label>
          </fieldset>
        </section>
      </StateBlock>

      <StateBlock v-if="tab === 'blocked'" :loading="blocked.loading.value" :error="blocked.error.value" :has-data="!!blocked.data.value" :empty="blocked.data.value && !blocked.data.value.length" empty-text="You haven't blocked anyone." @retry="blocked.reload">
        <section class="card">
          <p class="small muted">Blocked people can't follow you, send requests, nudges or invitations, see your profile or activity, and you won't see their chat messages.</p>
          <div class="list"><div v-for="u in blocked.data.value" :key="u.id" class="item"><span class="grow">{{ u.name }}</span><span class="tiny muted">since {{ ago(u.since) }}</span><button class="btn ghost sm" :disabled="busy" @click="unblock(u)">Unblock</button></div></div>
        </section>
      </StateBlock>

      <template v-if="tab === 'safety'">
        <section class="card">
          <h3>Account status</h3>
          <div v-if="!safety.data.value?.restrictions.length && !safety.data.value?.withheld_golden_nests.length" class="notice ok small">No restrictions on your account.</div>
          <div class="list">
            <div v-for="r in safety.data.value?.restrictions || []" :key="r.id" class="item">
              <div class="grow">
                <strong>{{ KIND[r.kind] }}</strong> <span class="chip" :class="r.active ? 'warn' : ''">{{ r.active ? 'Active' : 'Ended' }}</span>
                <div class="small muted">{{ r.reason }} · {{ ago(r.created_at) }}<template v-if="r.expires_at"> · until {{ new Date(r.expires_at).toLocaleDateString() }}</template></div>
                <div v-if="r.appeal" class="small">Appeal: <strong>{{ r.appeal.status }}</strong><template v-if="r.appeal.response"> — {{ r.appeal.response }}</template></div>
              </div>
              <button v-if="r.active && !r.appeal" class="btn secondary sm" @click="appealFor = r">Appeal</button>
            </div>
            <div v-for="(g, i) in safety.data.value?.withheld_golden_nests || []" :key="'g' + i" class="item small">Golden Nest from a race ({{ g.placement }} place) is pending review.</div>
          </div>
          <div v-if="appealFor" class="stack appeal">
            <label class="field">Tell the reviewers what happened<textarea v-model="appealText" class="input" rows="4" maxlength="3000" /></label>
            <div class="row"><button class="btn" :disabled="busy || appealText.trim().length < 10" @click="sendAppeal">Send appeal</button><button class="btn ghost" @click="appealFor = null">Cancel</button></div>
          </div>
        </section>
        <section class="card">
          <h3>Reports you've made</h3>
          <div v-if="!reports.data.value?.length" class="empty small">None.</div>
          <div class="list"><div v-for="r in reports.data.value || []" :key="r.id" class="item small"><span class="grow">{{ r.target_type }} · {{ r.category }} · {{ ago(r.created_at) }}</span><span class="chip">{{ r.status }}</span></div></div>
          <p class="tiny muted">Reports are confidential. Reviewers look at patterns and context; nothing happens to anyone automatically.</p>
        </section>
      </template>
    </div>
  </div>
</template>

<style scoped>
.body { margin-top: 16px; display: flex; flex-direction: column; gap: 14px; max-width: 860px; }
.box { border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 10px 14px; display: flex; flex-direction: column; gap: 8px; }
.box:disabled { opacity: .55; }
legend { font-weight: 800; }
hr { border: 0; border-top: 1px solid var(--border); margin: 18px 0; }
.ok { color: var(--leaf); font-weight: 700; }
.warn { color: var(--warn); font-weight: 700; }
.grow { flex: 1; min-width: 0; }
.appeal { margin-top: 12px; }
</style>
