<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import Modal from '../components/Modal.vue'
import StateBlock from '../components/StateBlock.vue'
import { api } from '../lib/api'
import { duration, fromLocalInput, toLocalInput, when } from '../lib/time'
import { useAction, useLoad } from '../lib/useLoad'
import { useSession } from '../stores/session'

const props = defineProps({ id: { type: String, required: true } })
const session = useSession()
const router = useRouter()
const { busy, run } = useAction(session)
const { data: m, loading, error, reload } = useLoad(() => api.get(`/meetings/${props.id}`))
const editing = ref(false)
const e = reactive({ title: '', starts_at: '', duration_minutes: 60, scope: 'this' })
const STATUS = { pending: ['warn', 'Waiting'], accepted: ['leaf', 'Going'], declined: ['', 'Declined'] }

function startEdit() {
  Object.assign(e, { title: m.value.title, starts_at: toLocalInput(m.value.starts_at), duration_minutes: m.value.duration_minutes, scope: 'this' })
  editing.value = true
}
async function save() {
  await run(() => api.patch(`/meetings/${props.id}`, { title: e.title, starts_at: fromLocalInput(e.starts_at), duration_minutes: e.duration_minutes, scope: e.scope }), 'Meeting updated. Invitees were notified.')
  editing.value = false
  reload()
}
async function cancel(scope) {
  const reason = prompt(scope === 'following' ? 'Cancel this and all following sessions. Reason (optional):' : 'Cancel this meeting. Reason (optional):', '')
  if (reason === null) return
  await run(() => api.post(`/meetings/${props.id}/cancel`, { scope, reason }), 'Cancelled. History is kept.')
  reload()
}
async function respond(accept) {
  await run(() => api.post(`/meetings/${props.id}/respond`, { accept }), accept ? 'See you there!' : 'Declined.')
  reload()
}
async function joinRoom() {
  await run(() => api.post(`/rooms/${m.value.room.id}/join`))
  router.push(`/rooms/${m.value.room.id}`)
}
async function report() {
  const details = prompt('Report this meeting to reviewers. What is wrong?')
  if (details === null) return
  await run(() => api.post('/reports', { target_type: 'meeting', target_id: props.id, category: 'spam', details }), 'Report sent.')
}
</script>

<template>
  <div class="page narrow">
    <StateBlock :loading="loading" :error="error" :has-data="!!m" @retry="reload">
      <template v-if="m">
        <RouterLink to="/meetings" class="small">← All meetings</RouterLink>
        <section class="card">
          <div class="row-between">
            <h1>{{ m.title }}</h1>
            <span class="chip" :class="{ scheduled: 'primary', live: 'leaf', cancelled: 'danger' }[m.status]">{{ m.status }}</span>
          </div>
          <p class="muted">{{ when(m.starts_at) }} · {{ duration(m.duration_minutes) }} · {{ m.subject }} · organised by {{ m.is_creator ? 'you' : m.creator.name }}</p>
          <p v-if="m.cancel_reason" class="notice danger small">Cancelled: {{ m.cancel_reason }}</p>
          <div v-if="m.topics.length" class="row"><span v-for="t in m.topics" :key="t" class="chip">{{ t }}</span></div>
          <p class="small muted">Reminders: {{ m.reminder_minutes.length ? m.reminder_minutes.map((x) => (x >= 60 ? `${x / 60} h` : `${x} min`)).join(', ') + ' before' : 'none' }}<template v-if="m.recurrence !== 'none'"> · repeats {{ m.recurrence }} (session {{ m.occurrence_index + 1 }})</template></p>

          <div class="row actions">
            <template v-if="m.my_response === 'pending' && m.status === 'scheduled'">
              <button class="btn leaf" :disabled="busy" @click="respond(true)">Accept</button>
              <button class="btn secondary" :disabled="busy" @click="respond(false)">Decline</button>
            </template>
            <template v-else-if="m.my_response && m.status === 'scheduled'">
              <span class="chip" :class="STATUS[m.my_response][0]">You: {{ STATUS[m.my_response][1] }}</span>
              <button class="btn ghost sm" :disabled="busy" @click="respond(m.my_response !== 'accepted')">{{ m.my_response === 'accepted' ? "Can't make it" : 'Accept instead' }}</button>
            </template>
            <template v-if="m.room && ['scheduled', 'studying'].includes(m.room.status) && (m.is_creator || m.my_response === 'accepted' || m.visibility === 'public')">
              <button class="btn" :disabled="busy" @click="joinRoom">{{ m.status === 'live' ? 'Join the room now' : 'Open room' }}</button>
            </template>
            <template v-if="m.is_creator && m.status === 'scheduled'">
              <button class="btn secondary sm" @click="startEdit">Edit</button>
              <button class="btn ghost sm" :disabled="busy" @click="cancel('this')">Cancel</button>
              <button v-if="m.series_id" class="btn ghost sm" :disabled="busy" @click="cancel('following')">Cancel this &amp; following</button>
            </template>
            <button v-if="!m.is_creator" class="btn ghost sm" @click="report">Report</button>
          </div>
        </section>
        <section v-if="m.invites.length" class="card">
          <h3>Invitations</h3>
          <div class="list">
            <div v-for="i in m.invites" :key="i.user_id" class="item"><RouterLink :to="`/u/${i.user_id}`" class="grow">{{ i.name }}</RouterLink><span class="chip" :class="STATUS[i.status][0]">{{ STATUS[i.status][1] }}</span></div>
          </div>
        </section>
      </template>
    </StateBlock>
    <Modal v-if="editing" title="Edit meeting" @close="editing = false">
      <form class="stack" @submit.prevent="save">
        <label class="field">Title<input v-model="e.title" class="input" maxlength="120" /></label>
        <label class="field">Start<input v-model="e.starts_at" type="datetime-local" class="input" /></label>
        <label class="field">Duration (minutes)<input v-model.number="e.duration_minutes" type="number" min="15" max="360" class="input" /></label>
        <div v-if="m.series_id" class="field">Apply to
          <label class="check"><input v-model="e.scope" type="radio" value="this" /> Only this session</label>
          <label class="check"><input v-model="e.scope" type="radio" value="following" /> This and all following sessions (times shift by the same amount)</label>
        </div>
        <button class="btn" :disabled="busy">Save</button>
      </form>
    </Modal>
  </div>
</template>

<style scoped>
.narrow { max-width: 820px; }
.page > * + * { margin-top: 12px; }
h1 { margin: 0; }
.actions { margin-top: 12px; }
.grow { flex: 1; }
</style>
