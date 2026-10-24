<script setup>
import { useRouter } from 'vue-router'
import RoomCard from '../components/RoomCard.vue'
import StateBlock from '../components/StateBlock.vue'
import { api } from '../lib/api'
import { ago } from '../lib/time'
import { useAction, useLoad } from '../lib/useLoad'
import { useSession } from '../stores/session'

const session = useSession()
const router = useRouter()
const { busy, run } = useAction(session)
const { data, loading, error, reload } = useLoad(() => api.get('/me/invites'))

async function respond(inv, action) {
  const r = await run(() => api.post(`/invites/${inv.id}`, { action }), action === 'accept' ? 'Joined!' : 'Invitation declined.')
  if (action === 'accept') router.push(`/rooms/${r.room_id}`)
  else reload()
}
async function report(inv) {
  if (!confirm(`Report this invitation from ${inv.inviter.name} as unwanted?`)) return
  await run(() => api.post('/reports', { target_type: 'invite', target_id: inv.id, category: 'spam' }), 'Reported.')
  await respond(inv, 'reject')
}
</script>

<template>
  <div class="page">
    <div class="page-head"><div><h1>Room invitations</h1><p>You're only added to a room if you accept. Meeting invitations live under Meetings.</p></div></div>
    <StateBlock :loading="loading" :error="error" :has-data="!!data" :empty="data && !data.length" empty-text="No pending invitations." @retry="reload">
      <div class="stack">
        <div v-for="inv in data" :key="inv.id" class="card">
          <p class="small"><strong>{{ inv.inviter.name }}</strong> invited you {{ ago(inv.created_at) }}</p>
          <RoomCard :room="inv.room" class="flat inner" />
          <div class="row">
            <button class="btn leaf" :disabled="busy" @click="respond(inv, 'accept')">Accept &amp; join</button>
            <button class="btn secondary" :disabled="busy" @click="respond(inv, 'reject')">Decline</button>
            <button class="btn ghost sm" :disabled="busy" @click="report(inv)">Report</button>
          </div>
        </div>
      </div>
    </StateBlock>
  </div>
</template>

<style scoped>
.inner { box-shadow: none; margin-bottom: 10px; }
.inner :deep(.act) { display: none; }
</style>
