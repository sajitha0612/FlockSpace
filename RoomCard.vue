<script setup>
import { computed } from 'vue'
import Bird from './Bird.vue'
import Icon from './Icon.vue'
import { duration, when } from '../lib/time'

const props = defineProps({ room: { type: Object, required: true }, busy: Boolean })
defineEmits(['join'])
const BIRDS = ['sparrow', 'bluebird', 'robin', 'goldfinch']
const TINTS = ['#dbe7fb', '#dff0dc', '#fde6d6', '#fbf0d0']
const idx = computed(() => [...props.room.subject].reduce((a, ch) => a + ch.charCodeAt(0), 0) % 4)
const statusChip = computed(() => ({ studying: ['leaf', 'Live now'], scheduled: ['primary', 'Upcoming'], race: ['gold', 'Nest Race'], finished: ['', 'Finished'], cancelled: ['danger', 'Cancelled'] }[props.room.status]))
const mine = computed(() => props.room.my_status === 'active')
</script>

<template>
  <article class="room card">
    <div class="pic" :style="{ background: TINTS[idx] }"><Bird :bird="{ color: BIRDS[idx] }" :size="64" label="" /></div>
    <div class="info">
      <div class="row">
        <RouterLink :to="`/rooms/${room.id}`" class="title">{{ room.title }}</RouterLink>
        <span class="chip" :class="statusChip[0]">{{ statusChip[1] }}</span>
        <span v-if="room.visibility === 'private'" class="chip"><Icon name="lock" :size="13" /> Private</span>
      </div>
      <div class="meta muted small">
        <span>{{ room.subject }}<template v-if="room.course"> · {{ room.course }}</template></span>
        <span class="nowrap"><Icon name="clock" :size="14" /> {{ duration(room.duration_minutes) }}</span>
        <span class="nowrap"><Icon name="users" :size="14" /> {{ room.participant_count }}/{{ room.max_participants }}</span>
        <span v-if="room.creator">by {{ room.creator.name }}</span>
      </div>
      <div class="small when"><Icon name="calendar" :size="14" /> {{ when(room.starts_at) }}</div>
      <div v-if="room.topics?.length" class="topics">
        <span v-for="t in room.topics.slice(0, 5)" :key="t" class="chip">{{ t }}</span>
        <span v-if="room.topics.length > 5" class="chip">+{{ room.topics.length - 5 }} more</span>
      </div>
    </div>
    <div class="act">
      <RouterLink v-if="mine" :to="`/rooms/${room.id}`" class="btn sm">Open</RouterLink>
      <button v-else-if="room.full" class="btn sm" disabled>Full</button>
      <button v-else class="btn sm" :disabled="busy" @click="$emit('join', room)">Join</button>
    </div>
  </article>
</template>

<style scoped>
.room { display: flex; gap: 14px; align-items: center; padding: 14px; }
.pic { width: 76px; height: 76px; border-radius: 14px; display: grid; place-items: center; flex: none; }
.info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.title { font-weight: 800; font-size: 1.05rem; color: var(--ink); }
.meta { display: flex; flex-wrap: wrap; gap: 4px 12px; }
.meta span, .when { display: inline-flex; align-items: center; gap: 4px; }
.topics { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 2px; }
.act { flex: none; }
@media (max-width: 520px) { .room { flex-wrap: wrap; } .pic { width: 56px; height: 56px; } .act { width: 100%; } .act .btn { width: 100%; } }
</style>
