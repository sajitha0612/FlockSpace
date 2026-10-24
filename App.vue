<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSession } from './stores/session'
import { realtime } from './lib/ws'
import { backend } from './lib/api'
import Bird from './components/Bird.vue'
import Icon from './components/Icon.vue'
import Logo from './components/Logo.vue'

const session = useSession()
const route = useRoute()
const router = useRouter()
const bare = computed(() => route.meta.bare || !session.signedIn)
const menuOpen = ref(false)

const nav = computed(() => [
  { to: '/home', label: 'Home', icon: 'home' },
  { to: '/rooms', label: 'Rooms', icon: 'rooms' },
  { to: '/meetings', label: 'Meetings', icon: 'calendar' },
  { to: '/buddies', label: 'Buddies', icon: 'buddies' },
  { to: '/progress', label: 'Progress', icon: 'chart' },
  { to: '/achievements', label: 'Achievements', icon: 'trophy' },
  { to: '/profile', label: 'My bird', icon: 'bird' },
  ...(session.isAdmin ? [{ to: '/review', label: 'Review', icon: 'shield' }] : []),
])

// live notifications: bump the bell, show a toast, and a system notification if the student allowed it
let off
onMounted(() => {
  off = realtime.on((evt) => {
    if (evt.type !== 'notification') return
    session.unread += 1
    session.toast(evt.data.title)
    if (evt.data.browser && 'Notification' in window && Notification.permission === 'granted' && document.hidden) {
      try { new Notification(evt.data.title, { body: evt.data.body, icon: '/favicon.svg', tag: evt.data.id }) } catch { /* unsupported */ }
    }
  })
})
onBeforeUnmount(() => off?.())

function toggleTheme() {
  const root = document.documentElement
  const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches
  root.dataset.theme = dark ? 'light' : 'dark'
  try { localStorage.setItem('flockspace.theme', root.dataset.theme) } catch { /* ignore */ }
}

function signOut() {
  session.signOut()
  router.push('/')
}
</script>

<template>
  <div v-if="bare" class="bare"><RouterView /></div>
  <div v-else class="shell">
    <aside class="side" :class="{ open: menuOpen }">
      <RouterLink to="/home" class="brand" @click="menuOpen = false"><Logo :size="34" /></RouterLink>
      <nav aria-label="Main">
        <RouterLink v-for="n in nav" :key="n.to" :to="n.to" class="nav-link" @click="menuOpen = false">
          <Icon :name="n.icon" /> <span>{{ n.label }}</span>
        </RouterLink>
      </nav>
      <div class="side-foot">
        <RouterLink to="/settings" class="nav-link" @click="menuOpen = false"><Icon name="settings" /> <span>Settings</span></RouterLink>
        <button class="nav-link as-btn" @click="signOut"><Icon name="logout" /> <span>Sign out</span></button>
      </div>
    </aside>
    <div class="main">
      <header class="top">
        <button class="icon-btn burger" aria-label="Open menu" @click="menuOpen = !menuOpen"><Icon name="menu" /></button>
        <div class="spacer" />
        <RouterLink v-if="backend.demo" to="/settings?tab=demo" class="demo-pill" title="The server isn’t reachable, so FlockSpace is running on sample data saved in this browser.">Offline demo</RouterLink>
        <div v-if="!session.user.email_verified" class="verify-pill">
          <RouterLink to="/verify">Verify your email</RouterLink>
        </div>
        <button class="icon-btn" aria-label="Toggle dark mode" @click="toggleTheme"><Icon name="moon" /></button>
        <RouterLink to="/invites" class="icon-btn" aria-label="Invitations"><Icon name="mail" /></RouterLink>
        <RouterLink to="/notifications" class="icon-btn bell" :aria-label="`Notifications, ${session.unread} unread`">
          <Icon name="bell" />
          <span v-if="session.unread" class="badge">{{ session.unread > 99 ? '99+' : session.unread }}</span>
        </RouterLink>
        <RouterLink to="/profile" class="me" aria-label="My profile">
          <Bird :bird="session.user.bird" :size="38" framed />
        </RouterLink>
      </header>
      <main id="content"><RouterView :key="$route.fullPath.split('?')[0]" /></main>
    </div>
    <div v-if="menuOpen" class="scrim" @click="menuOpen = false" />
  </div>
  <div class="toasts" role="status" aria-live="polite">
    <div v-for="t in session.toasts" :key="t.id" class="toast" :class="t.kind">{{ t.message }}</div>
  </div>
</template>

<style scoped>
.shell { display: grid; grid-template-columns: 230px minmax(0, 1fr); min-height: 100vh; }
.side { position: sticky; top: 0; height: 100vh; display: flex; flex-direction: column; gap: 6px; padding: 20px 14px; background: var(--surface); border-right: 1px solid var(--border); backdrop-filter: var(--glass-blur); -webkit-backdrop-filter: var(--glass-blur); }
.brand { font-size: 1.45rem; padding: 4px 8px 16px; text-decoration: none; }
.brand:hover { text-decoration: none; }
nav { display: flex; flex-direction: column; gap: 2px; }
.nav-link { display: flex; align-items: center; gap: 12px; padding: 9px 12px; border-radius: 12px; color: var(--ink-2); font-weight: 700; text-decoration: none; }
.nav-link:hover { background: var(--surface-3); text-decoration: none; }
.nav-link.router-link-active { background: var(--primary-soft); color: var(--primary); }
.as-btn { border: 0; background: none; font: inherit; cursor: pointer; text-align: left; width: 100%; }
.side-foot { margin-top: auto; display: flex; flex-direction: column; gap: 2px; }
.main { min-width: 0; }
.top { position: sticky; top: 0; z-index: 20; display: flex; align-items: center; gap: 6px; padding: 10px 20px; background: var(--surface-2); backdrop-filter: var(--glass-blur); -webkit-backdrop-filter: var(--glass-blur); border-bottom: 1px solid var(--border); }
.burger { display: none; }
.bell { position: relative; }
.badge { position: absolute; top: 0; right: -2px; background: var(--danger); color: #fff; font-size: .65rem; font-weight: 800; border-radius: 999px; padding: 1px 5px; }
.me { display: inline-flex; margin-left: 6px; }
.demo-pill { background: var(--twig-soft); color: var(--twig); border-radius: 999px; padding: 4px 12px; font-weight: 800; font-size: .8rem; text-decoration: none; }
.verify-pill { background: var(--warn-soft); border-radius: 999px; padding: 4px 12px; font-weight: 700; font-size: .85rem; }
.toasts { position: fixed; right: 16px; bottom: 16px; z-index: 100; display: flex; flex-direction: column; gap: 8px; max-width: min(360px, calc(100vw - 32px)); }
.toast { background: var(--ink); color: var(--bg); border-radius: 12px; padding: 10px 16px; box-shadow: var(--shadow-lg); font-weight: 600; animation: rise .25s ease; }
.toast.error { background: var(--danger); color: #fff; }
.toast.ok { background: var(--leaf); color: #fff; }
@keyframes rise { from { transform: translateY(8px); opacity: 0; } }
.scrim { display: none; }
@media (max-width: 860px) {
  .shell { grid-template-columns: minmax(0, 1fr); }
  .side { position: fixed; z-index: 50; left: 0; width: 250px; transform: translateX(-100%); transition: transform .2s; box-shadow: var(--shadow-lg); }
  .side.open { transform: none; }
  .burger { display: inline-flex; }
  .scrim { display: block; position: fixed; inset: 0; background: rgba(0, 0, 0, .3); z-index: 40; }
  .top { padding: 8px 12px; }
}
</style>
