<script setup>
import { onMounted, ref } from 'vue'
import TagInput from './TagInput.vue'
import { api } from '../lib/api'

const emit = defineEmits(['saved'])
const props = defineProps({ submitLabel: { type: String, default: 'Save profile' } })
const form = ref(null)
const goals = ref([])
const slots = ref([])
const zones = typeof Intl.supportedValuesOf === 'function' ? Intl.supportedValuesOf('timeZone') : []
const error = ref('')
const busy = ref(false)

onMounted(async () => {
  const d = await api.get('/me/profile')
  goals.value = d.goals_catalog
  slots.value = d.time_slots
  form.value = { name: d.user.name, bio: d.profile.bio, subjects: d.profile.subjects, courses: d.profile.courses, interests: d.profile.interests, year: d.profile.year,
                 goals: d.profile.goals, study_times: d.profile.study_times, timezone: d.profile.timezone, daily_goal_minutes: d.profile.daily_goal_minutes }
})

function toggle(list, v) {
  form.value[list] = form.value[list].includes(v) ? form.value[list].filter((x) => x !== v) : [...form.value[list], v]
}
const pretty = (s) => s.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())

async function save() {
  error.value = ''
  if (!form.value.subjects.length) { error.value = 'Add at least one subject so we can match you with rooms and buddies.'; return }
  busy.value = true
  try {
    emit('saved', await api.patch('/me/profile', form.value))
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
defineExpose({ save })
</script>

<template>
  <form v-if="form" class="stack" @submit.prevent="save">
    <div class="grid grid-2">
      <label class="field">Name<input v-model="form.name" class="input" maxlength="80" required /></label>
      <label class="field">Academic year
        <select v-model.number="form.year" class="input"><option :value="null">Prefer not to say</option><option v-for="y in 6" :key="y" :value="y">Year {{ y }}</option></select>
      </label>
    </div>
    <label class="field">Subjects <span class="hint">Press Enter after each, e.g. DSA, Web Development</span><TagInput v-model="form.subjects" placeholder="Add a subject" :max="12" /></label>
    <label class="field">Courses <span class="hint">Optional, e.g. CS201</span><TagInput v-model="form.courses" placeholder="Add a course" :max="8" /></label>
    <label class="field">Study interests<TagInput v-model="form.interests" placeholder="e.g. algorithms, UI design" :max="12" /></label>
    <div class="field">Learning goals
      <div class="opts"><button v-for="g in goals" :key="g" type="button" class="chip" :class="{ primary: form.goals.includes(g) }" :aria-pressed="form.goals.includes(g)" @click="toggle('goals', g)">{{ pretty(g) }}</button></div>
    </div>
    <div class="field">Preferred study times
      <div class="opts"><button v-for="s in slots" :key="s" type="button" class="chip" :class="{ primary: form.study_times.includes(s) }" :aria-pressed="form.study_times.includes(s)" @click="toggle('study_times', s)">{{ pretty(s) }}</button></div>
    </div>
    <div class="grid grid-2">
      <label class="field">Daily study goal (minutes) <span class="hint">Completed focus time that keeps your streak going</span>
        <input v-model.number="form.daily_goal_minutes" class="input" type="number" min="10" max="600" step="5" />
      </label>
      <label class="field">Timezone
        <select v-if="zones.length" v-model="form.timezone" class="input"><option v-for="z in zones" :key="z" :value="z">{{ z }}</option></select>
        <input v-else v-model="form.timezone" class="input" />
      </label>
    </div>
    <label class="field">Short bio <span class="hint">Optional, shown on your public profile</span><textarea v-model="form.bio" class="input" maxlength="300" rows="2" /></label>
    <p v-if="error" class="notice danger">{{ error }}</p>
    <button class="btn" :disabled="busy">{{ props.submitLabel }}</button>
  </form>
  <p v-else class="muted">Loading…</p>
</template>

<style scoped>
.opts { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.opts .chip { border: 1px solid var(--border); cursor: pointer; font: inherit; font-size: .85rem; font-weight: 700; }
</style>
