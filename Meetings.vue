<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import Icon from '../components/Icon.vue'
import Modal from '../components/Modal.vue'
import StateBlock from '../components/StateBlock.vue'
import TagInput from '../components/TagInput.vue'
import { api, idemKey } from '../lib/api'
import { duration, fromLocalInput, toLocalInput, when } from '../lib/time'
import { useAction, useLoad } from '../lib/useLoad'
import { useSession } from '../stores/session'

const session = useSession()
const router = useRouter()
const { busy, run } = useAction(session)
const past = ref(false)
const { data, loading, error, reload } = useLoad(() => api.get(`/meetings?past=${past.value}`))
watch(past, reload)
const creating = ref(false)
const people = ref([])
const conflicts = ref([])
const f = reactive({ title: '', subject: '', topics: [], starts_at: toLocalInput(Date.now() + 24 * 3600 * 1000), duration_minutes: 60, max_participants: 8,
  visibility: 'private', recurrence: 'none', occurrences: 4, reminders: [60, 10], invitees: [], key: idemKey() })
const STATUS = { scheduled: ['primary', 'Scheduled'], live: ['leaf', 'Happening now'], completed: ['', 'Completed'], cancelled: ['danger', 'Cancelled'] }

async function open() {
  creating.value = true
  f.key = idemKey()
  const c = await api.get('/me/connections')
  const seen = new Map()
  for (const u of [...c.buddies, ...c.followers, ...c.following]) seen.set(u.id, u)
  people.value = [...seen.values()]
  checkConflicts()
}
async function checkConflicts() {
  try { conflicts.value = await api.get(`/meetings/conflicts?starts_at=${encodeURIComponent(fromLocalInput(f.starts_at))}&duration_minutes=${f.duration_minutes}`) } catch { conflicts.value = [] }
}
watch(() => [f.starts_at, f.duration_minutes], () => creating.value && checkConflicts())
onMounted(() => { if (router.currentRoute.value.query.new) open() })

async function create() {
  const res = await run(() => api.post('/meetings', {
    title: f.title, subject: f.subject, topics: f.topics, starts_at: fromLocalInput(f.starts_at), duration_minutes: f.duration_minutes, max_participants: f.max_participants,
    visibility: f.visibility, recurrence: f.recurrence, occurrences: f.recurrence === 'none' ? 1 : f.occurrences, reminder_minutes: f.reminders, invitees: f.invitees, idempotency_key: f.key,
  }), 'Meeting scheduled. Invitees will be notified.')
  creating.value = false
  router.push(`/meetings/${res.meetings[0].id}`)
}
function toggleRem(m) { f.reminders = f.reminders.includes(m) ? f.reminders.filter((x) => x !== m) : [...f.reminders, m] }
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div><h1>Study meetings</h1><p>Plan sessions ahead. Times are shown in your timezone.</p></div>
      <button class="btn" @click="open"><Icon name="plus" :size="18" /> Schedule a meeting</button>
    </div>
    <div class="segmented"><button :class="{ on: !past }" @click="past = false">Upcoming</button><button :class="{ on: past }" @click="past = true">Past &amp; cancelled</button></div>
    <div class="body">
      <StateBlock :loading="loading" :error="error" :has-data="!!data" :empty="data && !data.length" :empty-text="past ? 'No past meetings.' : 'No upcoming meetings. Schedule one and invite your buddies!'" @retry="reload">
        <div class="stack">
          <RouterLink v-for="m in data" :key="m.id" :to="`/meetings/${m.id}`" class="card meeting">
            <div class="date"><strong>{{ new Date(m.starts_at).getDate() }}</strong><span>{{ new Date(m.starts_at).toLocaleDateString(undefined, { month: 'short' }) }}</span></div>
            <div class="grow">
              <div class="row"><strong class="title">{{ m.title }}</strong><span class="chip" :class="STATUS[m.status][0]">{{ STATUS[m.status][1] }}</span><span v-if="m.recurrence !== 'none'" class="chip">{{ m.recurrence }} · #{{ m.occurrence_index + 1 }}</span></div>
              <div class="small muted">{{ when(m.starts_at) }} · {{ duration(m.duration_minutes) }} · {{ m.subject }} · by {{ m.is_creator ? 'you' : m.creator.name }}</div>
            </div>
            <span v-if="m.my_response === 'pending'" class="chip warn">Reply needed</span>
            <span v-else-if="m.my_response" class="chip">{{ m.my_response }}</span>
          </RouterLink>
        </div>
      </StateBlock>
    </div>

    <Modal v-if="creating" title="Schedule a study meeting" wide @close="creating = false">
      <form class="stack" @submit.prevent="create">
        <div class="grid grid-2">
          <label class="field">Title<input v-model="f.title" class="input" maxlength="120" required /></label>
          <label class="field">Subject<input v-model="f.subject" class="input" maxlength="80" required /></label>
          <label class="field">Start<input v-model="f.starts_at" type="datetime-local" class="input" required /></label>
          <label class="field">Duration (minutes)<input v-model.number="f.duration_minutes" type="number" min="15" max="360" class="input" /></label>
          <label class="field">Participant limit<input v-model.number="f.max_participants" type="number" min="2" max="50" class="input" /></label>
          <label class="field">Room access<select v-model="f.visibility" class="input"><option value="private">Private (invitees only)</option><option value="public">Public</option></select></label>
          <label class="field">Repeat<select v-model="f.recurrence" class="input"><option value="none">Doesn't repeat</option><option value="daily">Daily</option><option value="weekly">Weekly</option></select></label>
          <label v-if="f.recurrence !== 'none'" class="field">Number of sessions<input v-model.number="f.occurrences" type="number" min="2" max="12" class="input" /></label>
        </div>
        <label class="field">Planned topics<TagInput v-model="f.topics" placeholder="Add topic" /></label>
        <div class="field">Reminders
          <div class="row"><label v-for="m in [1440, 60, 30, 10]" :key="m" class="check small"><input type="checkbox" :checked="f.reminders.includes(m)" @change="toggleRem(m)" /> {{ m >= 1440 ? '1 day' : m >= 60 ? '1 hour' : `${m} min` }} before</label></div>
          <span class="hint">You and everyone who accepts get these, plus a notice when it starts, even if FlockSpace isn't open.</span>
        </div>
        <div class="field">Invite <span class="hint">Followers and buddies. They join only if they accept.</span>
          <div v-if="!people.length" class="small muted">Follow people or add buddies to invite them.</div>
          <div class="row"><label v-for="u in people" :key="u.id" class="check small"><input v-model="f.invitees" type="checkbox" :value="u.id" /> {{ u.name }}</label></div>
        </div>
        <div v-if="conflicts.length" class="notice warn small">Heads up: this overlaps with {{ conflicts.map((c) => `${c.title} (${when(c.starts_at)})`).join(', ') }}. You can still schedule it.</div>
        <p class="small muted">A study room is created for each session, opening at the meeting time.<template v-if="f.recurrence !== 'none'"> Editing or cancelling later lets you change just one session or this and all following ones.</template></p>
        <button class="btn" :disabled="busy">Schedule</button>
      </form>
    </Modal>
  </div>
</template>

<style scoped>
.body { margin-top: 14px; }
.meeting { display: flex; gap: 14px; align-items: center; color: var(--ink); text-decoration: none; }
.meeting:hover { border-color: var(--border-strong); text-decoration: none; }
.date { width: 56px; height: 56px; border-radius: 14px; background: var(--primary-soft); color: var(--primary); display: flex; flex-direction: column; align-items: center; justify-content: center; flex: none; }
.date strong { font-size: 1.3rem; line-height: 1; }
.date span { font-size: .75rem; font-weight: 700; }
.grow { flex: 1; min-width: 0; }
.title { font-size: 1.05rem; }
</style>
