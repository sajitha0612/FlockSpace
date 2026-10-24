<script setup>
import { reactive, ref } from 'vue'
import Modal from '../components/Modal.vue'
import StateBlock from '../components/StateBlock.vue'
import { api } from '../lib/api'
import { ago } from '../lib/time'
import { useAction, useLoad } from '../lib/useLoad'
import { useSession } from '../stores/session'

const session = useSession()
const { busy, run } = useAction(session)
const { data, loading, error, reload } = useLoad(() => api.get('/admin/queue'))
const restricting = ref(null)
const r = reactive({ kind: 'chat_ban', reason: '', days: 7 })
const FLAG = { repeated_small_group: 'Same small group, same winner, many races', new_account_win_shared_network: 'New account won, shares a network with a racer', golden_withheld: 'Golden Nest withheld', many_signups_one_network: 'Many signups from one network' }

async function resolve(rep, status) {
  const resolution = prompt('Internal note (never shown to the reported person):', '') ?? ''
  await run(() => api.post(`/admin/reports/${rep.id}`, { status, resolution }), 'Report closed.')
  reload()
}
async function flag(f, status, release = false) {
  await run(() => api.post(`/admin/flags/${f.id}`, { status, release_golden: release }), 'Flag reviewed.')
  reload()
}
async function restrict() {
  await run(() => api.post('/admin/restrictions', { user_id: restricting.value.id, kind: r.kind, reason: r.reason, days: r.days || null }), 'Restriction applied. The student was notified and can appeal.')
  restricting.value = null
}
async function decide(a, overturn) {
  const response = prompt(overturn ? 'Message to the student (restriction will be lifted):' : 'Explain why the restriction stays:', '')
  if (!response) return
  await run(() => api.post(`/admin/appeals/${a.id}`, { overturn, response }), 'Appeal decided.')
  reload()
}
</script>

<template>
  <div class="page">
    <div class="page-head"><div><h1>Review queue</h1><p>Flags are signals for a human look, not proof. Act only after checking the context.</p></div><button class="btn secondary sm" @click="reload">Refresh</button></div>
    <StateBlock :loading="loading" :error="error" :has-data="!!data" @retry="reload">
      <template v-if="data">
        <section class="card">
          <h3>Reports ({{ data.reports.length }})</h3>
          <div v-if="!data.reports.length" class="empty small">No open reports.</div>
          <div class="list">
            <div v-for="rep in data.reports" :key="rep.id" class="item top">
              <div class="grow">
                <strong>{{ rep.category }}</strong> · {{ rep.target_type }} · against <RouterLink :to="`/u/${rep.target_user.id}`">{{ rep.target_user.name }}</RouterLink> · by {{ rep.reporter }} · {{ ago(rep.created_at) }}
                <p v-if="rep.details" class="small">{{ rep.details }}</p>
                <blockquote v-if="rep.evidence?.text" class="quote small">{{ rep.evidence.text }}</blockquote>
              </div>
              <div class="stack acts">
                <button class="btn sm secondary" @click="restricting = rep.target_user">Restrict…</button>
                <button class="btn sm" :disabled="busy" @click="resolve(rep, 'resolved')">Resolve</button>
                <button class="btn sm ghost" :disabled="busy" @click="resolve(rep, 'dismissed')">Dismiss</button>
              </div>
            </div>
          </div>
        </section>
        <section class="card">
          <h3>Risk flags ({{ data.flags.length }})</h3>
          <div v-if="!data.flags.length" class="empty small">No open flags.</div>
          <div class="list">
            <div v-for="f in data.flags" :key="f.id" class="item top">
              <div class="grow"><strong>{{ FLAG[f.kind] || f.kind }}</strong><template v-if="f.user.id"> · <RouterLink :to="`/u/${f.user.id}`">{{ f.user.name }}</RouterLink></template> · {{ ago(f.created_at) }}
                <pre class="small details">{{ JSON.stringify(f.details, null, 1) }}</pre></div>
              <div class="stack acts">
                <button v-if="f.kind === 'golden_withheld'" class="btn sm leaf" :disabled="busy" @click="flag(f, 'dismissed', true)">Release Golden Nest</button>
                <button v-if="f.user.id" class="btn sm secondary" @click="restricting = f.user">Restrict…</button>
                <button class="btn sm ghost" :disabled="busy" @click="flag(f, 'dismissed')">Dismiss</button>
                <button class="btn sm ghost" :disabled="busy" @click="flag(f, 'actioned')">Mark actioned</button>
              </div>
            </div>
          </div>
        </section>
        <section class="card">
          <h3>Appeals ({{ data.appeals.length }})</h3>
          <div v-if="!data.appeals.length" class="empty small">No open appeals.</div>
          <div class="list">
            <div v-for="a in data.appeals" :key="a.id" class="item top">
              <div class="grow"><strong>{{ a.user.name }}</strong> · {{ a.restriction.kind }}: {{ a.restriction.reason }} · {{ ago(a.created_at) }}<p class="small">{{ a.text }}</p></div>
              <div class="stack acts"><button class="btn sm leaf" :disabled="busy" @click="decide(a, true)">Overturn</button><button class="btn sm ghost" :disabled="busy" @click="decide(a, false)">Uphold</button></div>
            </div>
          </div>
        </section>
      </template>
    </StateBlock>
    <Modal v-if="restricting" :title="`Restrict ${restricting.name}`" @close="restricting = null">
      <form class="stack" @submit.prevent="restrict">
        <label class="field">Type<select v-model="r.kind" class="input"><option value="chat_ban">Restrict chat</option><option value="reward_hold">Hold new Golden Nests for review</option><option value="suspended">Suspend account</option></select></label>
        <label class="field">Reason (shown to the student)<input v-model="r.reason" class="input" minlength="5" maxlength="300" required /></label>
        <label class="field">Days <span class="hint">empty = until lifted</span><input v-model.number="r.days" type="number" min="1" max="365" class="input" /></label>
        <p class="small muted">Existing rewards are never removed. The student is notified and can appeal.</p>
        <button class="btn danger" :disabled="busy">Apply</button>
      </form>
    </Modal>
  </div>
</template>

<style scoped>
.page > section + section { margin-top: 14px; }
.top { align-items: flex-start; }
.grow { flex: 1; min-width: 0; }
.acts { min-width: 150px; }
.quote { margin: 6px 0; padding: 6px 10px; border-left: 3px solid var(--border-strong); background: var(--surface-2); white-space: pre-wrap; }
.details { white-space: pre-wrap; background: var(--surface-2); padding: 6px 10px; border-radius: 8px; max-height: 160px; overflow: auto; }
</style>
