<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import Bird from '../components/Bird.vue'
import Icon from '../components/Icon.vue'
import TagInput from '../components/TagInput.vue'
import { api } from '../lib/api'
import { fromLocalInput, toLocalInput } from '../lib/time'
import { useSession } from '../stores/session'

const session = useSession()
const router = useRouter()
const startNow = ref(true)
const form = ref({
  title: '', subject: '', course: '', year: null, description: '', topics: [],
  starts_at: toLocalInput(Date.now() + 60 * 60 * 1000), duration_minutes: 120, max_participants: 10, visibility: 'public',
  ai_assistant_enabled: true, ai_notes_enabled: true, quiz: { question_count: 10, minutes: 10, placement_bonuses: [3, 2, 1] },
})
const error = ref('')
const busy = ref(false)
// study materials picked here are uploaded to the room's Resources right after it's created
const ACCEPT = ['.pdf', '.docx', '.pptx', '.txt', '.md']
const MAX_MB = 15
const docs = ref([])
const picker = ref(null)
const docError = ref('')
const size = (n) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`)
function addDocs(e) {
  docError.value = ''
  for (const f of e.target.files) {
    const ext = f.name.slice(f.name.lastIndexOf('.')).toLowerCase()
    if (!ACCEPT.includes(ext)) docError.value = `${f.name}: only PDF, Word, PowerPoint, .txt and .md files are supported.`
    else if (f.size > MAX_MB * 1048576) docError.value = `${f.name} is larger than ${MAX_MB} MB.`
    else if (docs.value.length >= 10) docError.value = 'You can attach up to 10 documents here. Add more from the room later.'
    else if (!docs.value.some((d) => d.name === f.name && d.size === f.size)) docs.value.push(f)
  }
  e.target.value = ''
}
async function uploadDocs(roomId) {
  let failed = 0
  for (const f of docs.value) {
    const fd = new FormData()
    fd.append('file', f)
    fd.append('title', f.name.replace(/\.[^.]+$/, ''))
    try { await api.upload(`/rooms/${roomId}/resources/file`, fd) } catch { failed++ }
  }
  if (failed) session.toast(`${failed} document${failed > 1 ? 's' : ''} couldn't be uploaded. You can retry from the Resources tab.`, 'error')
}
const durations = [30, 45, 60, 90, 120, 150, 180, 240]
const valid = computed(() => form.value.title.trim().length >= 3 && form.value.subject.trim().length >= 2 && form.value.topics.length)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    const body = { ...form.value, starts_at: startNow.value ? new Date().toISOString() : fromLocalInput(form.value.starts_at) }
    const room = await api.post('/rooms', body)
    if (docs.value.length) await uploadDocs(room.id)
    session.toast(docs.value.length ? `Room created with ${docs.value.length} document${docs.value.length > 1 ? 's' : ''}!` : 'Room created!', 'ok')
    router.push(`/rooms/${room.id}?tab=manage`)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="layout">
      <form class="card stack" @submit.prevent="submit">
        <div>
          <h1>Create a study room</h1>
          <p class="muted">Plan your session and invite your flock.</p>
        </div>
        <label class="field">Room title<input v-model="form.title" class="input" maxlength="100" placeholder="e.g. DSA Fundamentals" required /></label>
        <div class="grid grid-2">
          <label class="field">Subject<input v-model="form.subject" class="input" maxlength="80" placeholder="e.g. Data Structures & Algorithms" required /></label>
          <label class="field">Course <span class="hint">optional</span><input v-model="form.course" class="input" maxlength="80" placeholder="e.g. CS201" /></label>
        </div>
        <label class="field">Topics to cover <span class="hint">Everyone gets this checklist. Press Enter after each topic.</span>
          <TagInput v-model="form.topics" placeholder="Add topic" :max="30" label="Add topic" />
        </label>
        <label class="field">Description <span class="hint">optional</span><textarea v-model="form.description" class="input" maxlength="500" rows="2" /></label>
        <div class="grid grid-2">
          <div class="field">Start time
            <label class="check"><input v-model="startNow" type="checkbox" /> Start right away</label>
            <input v-if="!startNow" v-model="form.starts_at" type="datetime-local" class="input" required />
          </div>
          <label class="field">Total study duration
            <select v-model.number="form.duration_minutes" class="input"><option v-for="d in durations" :key="d" :value="d">{{ d >= 60 ? `${d / 60} hour${d > 60 ? 's' : ''}` : `${d} minutes` }}</option></select>
            <span class="hint">You control this. Individual Pomodoro cycles never change the end time.</span>
          </label>
          <label class="field">Max participants<input v-model.number="form.max_participants" type="number" class="input" min="2" max="50" /></label>
          <div class="field">Room type
            <div class="row">
              <label class="check"><input v-model="form.visibility" type="radio" value="public" /> Public</label>
              <label class="check"><input v-model="form.visibility" type="radio" value="private" /> Private (invite or join code)</label>
            </div>
          </div>
        </div>
        <fieldset class="box">
          <legend>Study materials</legend>
          <p class="small muted">Share notes, slides or past papers with everyone who joins. PDF, Word, PowerPoint, .txt or .md, up to {{ MAX_MB }} MB each.</p>
          <input ref="picker" type="file" multiple :accept="ACCEPT.join(',')" class="sr-only" tabindex="-1" @change="addDocs" />
          <div><button type="button" class="btn secondary" @click="picker.click()"><Icon name="upload" :size="17" /> Upload documents</button></div>
          <ul v-if="docs.length" class="docs">
            <li v-for="(d, i) in docs" :key="d.name + d.size" class="doc glass">
              <Icon name="file" :size="18" />
              <span class="grow">{{ d.name }}</span>
              <span class="small muted">{{ size(d.size) }}</span>
              <button type="button" class="icon-btn" :aria-label="`Remove ${d.name}`" @click="docs.splice(i, 1)"><Icon name="trash" :size="15" /></button>
            </li>
          </ul>
          <p v-if="docError" class="small fail">{{ docError }}</p>
        </fieldset>
        <fieldset class="box">
          <legend>Final quiz: the Nest Race</legend>
          <p class="small muted">Starts automatically when the study phase ends and covers every topic. You'll add or import questions after creating the room. As the creator you can see the answers, so you race for practice only.</p>
          <div class="grid grid-3">
            <label class="field">Questions<input v-model.number="form.quiz.question_count" type="number" class="input" min="4" max="30" /></label>
            <label class="field">Time limit (min)<input v-model.number="form.quiz.minutes" type="number" class="input" min="3" max="60" /></label>
            <label class="field">Bonus twigs 1st/2nd/3rd
              <div class="row nowrap"><input v-for="(b, i) in form.quiz.placement_bonuses" :key="i" v-model.number="form.quiz.placement_bonuses[i]" type="number" class="input bonus" min="0" max="10" :aria-label="`Bonus for place ${i + 1}`" /></div>
            </label>
          </div>
          <p class="small muted">Winners: more than 5 eligible racers → top 3 win Golden Nests; 5 or fewer → only 1st. These rules lock when the race starts.</p>
        </fieldset>
        <fieldset class="box">
          <legend>AI help</legend>
          <label class="check"><input v-model="form.ai_assistant_enabled" type="checkbox" /> AI study agent in this room</label>
          <label class="check"><input v-model="form.ai_notes_enabled" type="checkbox" /> AI notes, document summaries and task lists</label>
        </fieldset>
        <p v-if="error" class="notice danger" role="alert">{{ error }}</p>
        <div class="row"><button class="btn lg" :disabled="busy || !valid">Create room</button><RouterLink to="/rooms" class="btn ghost">Cancel</RouterLink></div>
      </form>
      <aside class="side-art" aria-hidden="true">
        <Bird :bird="{ color: 'sparrow', accessory: 'accessory_cap' }" :size="150" mood="idle" />
        <p class="hand">Great minds study together!</p>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.layout { display: grid; grid-template-columns: minmax(0, 1fr) 260px; gap: 20px; align-items: start; }
.box { border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 12px 14px; display: flex; flex-direction: column; gap: 8px; }
legend { font-weight: 800; padding: 0 4px; }
.bonus { width: 64px; }
.docs { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.doc { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: var(--radius-sm); }
.doc .grow { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; }
.fail { color: var(--danger); margin: 0; }
.side-art { position: sticky; top: 90px; text-align: center; }
@media (max-width: 860px) { .layout { grid-template-columns: 1fr; } .side-art { display: none; } }
</style>
