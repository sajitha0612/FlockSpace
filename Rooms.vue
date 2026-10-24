<script setup>
import { reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import Icon from '../components/Icon.vue'
import RoomCard from '../components/RoomCard.vue'
import StateBlock from '../components/StateBlock.vue'
import Modal from '../components/Modal.vue'
import { api } from '../lib/api'
import { useAction, useLoad } from '../lib/useLoad'
import { useSession } from '../stores/session'

const session = useSession()
const router = useRouter()
const f = reactive({ q: '', subject: '', course: '', topic: '', year: '', when: 'any', available: false, interests: false, sort: 'soonest' })
const tab = ref('discover')
const query = () => new URLSearchParams(Object.entries(f).filter(([, v]) => v !== '' && v !== false).map(([k, v]) => [k, String(v)])).toString()
const { data, loading, error, reload } = useLoad(() => api.get(`/rooms?${query()}`))
const mine = useLoad(() => api.get('/rooms/mine'))
const { busy, run } = useAction(session)
const codeFor = ref(null)
const code = ref('')

let t
watch(f, () => { clearTimeout(t); t = setTimeout(reload, 300) })

async function join(room, withCode) {
  if (room.visibility === 'private' && !withCode && room.my_status !== 'active') { codeFor.value = room; return }
  await run(() => api.post(`/rooms/${room.id}/join`, withCode ? { code: code.value } : {}), `Joined ${room.title}`)
  router.push(`/rooms/${room.id}`)
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div><h1>Study rooms</h1><p>Find your flock, or start a room of your own.</p></div>
      <RouterLink to="/rooms/new" class="btn"><Icon name="plus" :size="18" /> Create a room</RouterLink>
    </div>
    <div class="tabs" role="tablist">
      <button :class="{ on: tab === 'discover' }" role="tab" :aria-selected="tab === 'discover'" @click="tab = 'discover'">Discover</button>
      <button :class="{ on: tab === 'mine' }" role="tab" :aria-selected="tab === 'mine'" @click="tab = 'mine'">My rooms</button>
    </div>

    <template v-if="tab === 'discover'">
      <div class="card filters">
        <label class="search"><Icon name="search" /><input v-model="f.q" class="input" placeholder="Search rooms, subjects or topics…" aria-label="Search rooms" /></label>
        <div class="row">
          <select v-model="f.subject" class="input sel" aria-label="Subject"><option value="">All subjects</option><option v-for="s in data?.subjects || []" :key="s" :value="s">{{ s }}</option></select>
          <input v-model="f.topic" class="input sel" placeholder="Topic" aria-label="Topic" />
          <input v-model="f.course" class="input sel" placeholder="Course" aria-label="Course" />
          <select v-model="f.year" class="input sel" aria-label="Year"><option value="">Any year</option><option v-for="y in 6" :key="y" :value="y">Year {{ y }}</option></select>
          <select v-model="f.when" class="input sel" aria-label="Schedule"><option value="any">Any time</option><option value="live">Live now</option><option value="today">Next 24 hours</option><option value="week">This week</option><option value="later">Later</option></select>
          <select v-model="f.sort" class="input sel" aria-label="Sort"><option value="soonest">Soonest</option><option value="popular">Most popular</option><option value="newest">Newest</option></select>
          <label class="check small"><input v-model="f.available" type="checkbox" /> Has space</label>
          <label class="check small"><input v-model="f.interests" type="checkbox" /> Matches my interests</label>
        </div>
      </div>
      <StateBlock :loading="loading" :error="error" :has-data="!!data" :empty="data && !data.rooms.length" @retry="reload">
        <template #empty>
          <p class="muted">No rooms match those filters.</p>
          <RouterLink to="/rooms/new" class="btn sm">Create one</RouterLink>
        </template>
        <div class="stack"><RoomCard v-for="r in data.rooms" :key="r.id" :room="r" :busy="busy" @join="join" /></div>
      </StateBlock>
    </template>

    <template v-else>
      <StateBlock :loading="mine.loading.value" :error="mine.error.value" :has-data="!!mine.data.value" @retry="mine.reload">
        <template v-if="mine.data.value">
          <h3 class="sec">Active &amp; upcoming</h3>
          <div v-if="!mine.data.value.active.length" class="empty small">None yet.</div>
          <div class="stack"><RoomCard v-for="r in mine.data.value.active" :key="r.id" :room="r" /></div>
          <h3 class="sec">Past rooms</h3>
          <div v-if="!mine.data.value.past.length" class="empty small">Finished rooms will be listed here.</div>
          <div class="stack"><RoomCard v-for="r in mine.data.value.past" :key="r.id" :room="r" /></div>
        </template>
      </StateBlock>
    </template>

    <Modal v-if="codeFor" title="Private room" @close="codeFor = null">
      <form class="stack" @submit.prevent="join(codeFor, true)">
        <p class="muted">Enter the join code from the room's creator, or ask them for an invitation.</p>
        <input v-model="code" class="input" maxlength="12" placeholder="Join code" required />
        <button class="btn" :disabled="busy">Join</button>
      </form>
    </Modal>
  </div>
</template>

<style scoped>
.filters { margin: 16px 0; display: flex; flex-direction: column; gap: 10px; }
.search { display: flex; align-items: center; gap: 8px; color: var(--muted); }
.sel { width: auto; min-width: 120px; flex: 1 1 140px; }
.sec { margin: 18px 0 10px; }
</style>
