import { createRouter, createWebHistory } from 'vue-router'
import { useSession } from './stores/session'

const routes = [
  { path: '/', name: 'landing', component: () => import('./views/Landing.vue'), meta: { public: true, bare: true } },
  { path: '/login', name: 'login', component: () => import('./views/auth/Login.vue'), meta: { public: true, bare: true } },
  { path: '/signup', name: 'signup', component: () => import('./views/auth/Signup.vue'), meta: { public: true, bare: true } },
  { path: '/forgot', name: 'forgot', component: () => import('./views/auth/Forgot.vue'), meta: { public: true, bare: true } },
  { path: '/verify', name: 'verify', component: () => import('./views/auth/Verify.vue'), meta: { bare: true } },
  { path: '/welcome', name: 'onboarding', component: () => import('./views/Onboarding.vue') },
  { path: '/home', name: 'dashboard', component: () => import('./views/Dashboard.vue') },
  { path: '/progress', name: 'progress', component: () => import('./views/Progress.vue') },
  { path: '/rooms', name: 'rooms', component: () => import('./views/Rooms.vue') },
  { path: '/rooms/new', name: 'create-room', component: () => import('./views/CreateRoom.vue') },
  { path: '/rooms/:id', name: 'room', component: () => import('./views/room/Room.vue'), props: true },
  { path: '/buddies', name: 'buddies', component: () => import('./views/Buddies.vue') },
  { path: '/u/:id', name: 'user', component: () => import('./views/PublicProfile.vue'), props: true },
  { path: '/profile', name: 'profile', component: () => import('./views/Profile.vue') },
  { path: '/achievements', name: 'achievements', component: () => import('./views/Achievements.vue') },
  { path: '/meetings', name: 'meetings', component: () => import('./views/Meetings.vue') },
  { path: '/meetings/:id', name: 'meeting', component: () => import('./views/MeetingDetail.vue'), props: true },
  { path: '/invites', name: 'invites', component: () => import('./views/Invites.vue') },
  { path: '/notifications', name: 'notifications', component: () => import('./views/Notifications.vue') },
  { path: '/settings', name: 'settings', component: () => import('./views/Settings.vue') },
  { path: '/review', name: 'admin', component: () => import('./views/Admin.vue') },
  { path: '/:rest(.*)*', name: 'missing', component: () => import('./views/NotFound.vue'), meta: { public: true } },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: (to, from, saved) => saved || (to.path !== from.path ? { top: 0 } : undefined),
})

router.beforeEach(async (to) => {
  const session = useSession()
  if (!session.loaded) await session.load()  // the first navigation must wait for the stored session
  if (!to.meta.public && !session.signedIn) return { name: 'login', query: { next: to.fullPath } }
  if (session.signedIn && ['landing', 'login', 'signup'].includes(to.name)) return { name: 'dashboard' }
  // Onboarding is encouraged (Home shows a reminder) but never blocks navigation: every page works with a partial profile.
})
