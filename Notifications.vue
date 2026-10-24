<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Icon from '../components/Icon.vue'
import StateBlock from '../components/StateBlock.vue'
import { api } from '../lib/api'
import { ago } from '../lib/time'
import { useLoad } from '../lib/useLoad'
import { useSession } from '../stores/session'

const session = useSession()
const router = useRouter()
const { data, loading, error, reload } = useLoad(() => api.get('/notifications'))
onMounted(() => session.refreshUnread())
const ICON = { meeting_reminder: 'calendar', meeting_invite: 'calendar', meeting_response: 'calendar', meeting_update: 'calendar', room_invite: 'mail', buddy_request: 'buddies',
  buddy_accepted: 'buddies', follow: 'buddies', nudge: 'hand', race_start: 'trophy', race_result: 'trophy', golden_nest: 'trophy', item_unlocked: 'sparkle', halfway_unlocked: 'check',
  ai_done: 'sparkle', ai_failed: 'x', moderation: 'shield', report_update: 'shield', room_update: 'rooms' }

async function open(n) {
  if (!n.read) {
    await api.post(`/notifications/${n.id}/read`)
    n.read = true
    session.unread = Math.max(0, session.unread - 1)
  }
  if (n.link) router.push(n.link)
}
async function readAll() {
  await api.post('/notifications/read-all')
  session.unread = 0
  reload()
}
</script>

<template>
  <div class="page narrow">
    <div class="page-head">
      <div><h1>Notifications</h1></div>
      <button class="btn secondary sm" @click="readAll">Mark all read</button>
    </div>
    <StateBlock :loading="loading" :error="error" :has-data="!!data" :empty="data && !data.items.length" empty-text="You're all caught up." @retry="reload">
      <div class="card list">
        <button v-for="n in data.items" :key="n.id" class="item notif" :class="{ unread: !n.read }" @click="open(n)">
          <span class="ic"><Icon :name="ICON[n.type] || 'bell'" /></span>
          <span class="grow"><strong>{{ n.title }}</strong><span v-if="n.body" class="small muted body">{{ n.body }}</span></span>
          <span class="tiny muted nowrap">{{ ago(n.created_at) }}</span>
        </button>
      </div>
    </StateBlock>
    <p class="small muted">System notifications (when FlockSpace is in the background) can be turned on in <RouterLink to="/settings">Settings</RouterLink>.</p>
  </div>
</template>

<style scoped>
.narrow { max-width: 760px; }
.notif { width: 100%; border: 0; background: none; font: inherit; color: inherit; text-align: left; cursor: pointer; padding: 12px 8px; border-radius: 10px; }
.notif:hover { background: var(--surface-2); }
.notif.unread { background: var(--primary-soft); }
.ic { width: 36px; height: 36px; border-radius: 50%; background: var(--surface-3); display: grid; place-items: center; flex: none; }
.grow { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.body { overflow-wrap: anywhere; }
</style>
