import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { detectBackend, setUnauthorizedHandler } from './lib/api'
import { useSession } from './stores/session'
import './style.css'

try {
  const theme = localStorage.getItem('flockspace.theme')
  if (theme) document.documentElement.dataset.theme = theme
} catch { /* storage unavailable */ }

const app = createApp(App)
app.use(createPinia())
const session = useSession()
setUnauthorizedHandler(() => {
  session.signOut()
  router.push({ name: 'login', query: { next: router.currentRoute.value.fullPath } })
})
// pick server or offline demo before the first navigation loads the session
detectBackend().then(() => {
  app.use(router)
  return router.isReady()
}).then(() => app.mount('#app'))
