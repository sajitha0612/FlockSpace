<script setup>
// Small stroke icon set (24px grid). Decorative: the surrounding text or aria-label carries the meaning.
defineProps({ name: { type: String, required: true }, size: { type: Number, default: 20 } })
const paths = {
  home: 'M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z',
  rooms: 'M4 5h16v10H4zM8 19h8M12 15v4',
  calendar: 'M4 6h16v14H4zM4 10h16M8 3v4M16 3v4',
  buddies: 'M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM2.5 20c.6-3.4 3.2-5.5 6.5-5.5s5.9 2.1 6.5 5.5M16 4.5a3.3 3.3 0 0 1 0 6.4M18 14.6c2 .7 3.2 2.6 3.5 5.4',
  chart: 'M4 20V10M10 20V4M16 20v-7M22 20H2',
  trophy: 'M8 4h8v5a4 4 0 0 1-8 0zM8 6H4a3 3 0 0 0 4 4M16 6h4a3 3 0 0 1-4 4M12 13v4M8 21h8M9 17h6',
  bird: 'M4 15c0-5 4-9 9-9 2.5 0 4.5 2 4.5 4.5L21 12l-3.4 1.2C16.6 17 13.5 19 10 19H4l3-2c-2-.2-3-1-3-2zM14 9.5h.01',
  shield: 'M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6z',
  settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
  logout: 'M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 17l-5-5 5-5M5 12h11',
  menu: 'M4 6h16M4 12h16M4 18h16',
  moon: 'M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z',
  mail: 'M3 6h18v12H3zM3 7l9 6 9-6',
  bell: 'M6 16V11a6 6 0 1 1 12 0v5l2 2H4zM10 20a2 2 0 0 0 4 0',
  search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4',
  plus: 'M12 5v14M5 12h14',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2',
  users: 'M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM2.5 20c.6-3.4 3.2-5.5 6.5-5.5s5.9 2.1 6.5 5.5',
  check: 'M5 12l5 5 9-10',
  idcard: 'M3 6h18v12H3zM8 10.5a1.8 1.8 0 1 0 0.01 0M5.5 15.5c.6-1.4 1.5-2 2.5-2s1.9.6 2.5 2M13 10h5M13 13h4',
  x: 'M6 6l12 12M18 6L6 18',
  play: 'M8 5l11 7-11 7z',
  pause: 'M8 5h3v14H8zM13 5h3v14h-3z',
  stop: 'M6 6h12v12H6z',
  coffee: 'M4 9h13v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5zM17 10h1.5a2.5 2.5 0 0 1 0 5H17M8 3v3M12 3v3',
  send: 'M4 12l16-8-6 16-2.5-6.5z',
  upload: 'M12 16V4M7 9l5-5 5 5M4 20h16',
  link: 'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1',
  file: 'M6 3h8l4 4v14H6zM14 3v4h4',
  sparkle: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z',
  flag: 'M5 21V4M5 4h11l-2 4 2 4H5',
  lock: 'M6 11h12v10H6zM8 11V7a4 4 0 0 1 8 0v4',
  globe: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3 12h18M12 3c2.5 2.5 3.5 5.5 3.5 9s-1 6.5-3.5 9c-2.5-2.5-3.5-5.5-3.5-9s1-6.5 3.5-9z',
  twig: 'M4 20L20 4M9 15l-4-1M14 10l1-5M12 12l5 2',
  download: 'M12 4v12M7 11l5 5 5-5M4 20h16',
  copy: 'M8 8h12v12H8zM4 16V4h12',
  trash: 'M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3',
  edit: 'M4 20h4L19 9l-4-4L4 16zM14 6l4 4',
  refresh: 'M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7',
  hand: 'M8 13V5.5a1.5 1.5 0 0 1 3 0V11M11 10V4.5a1.5 1.5 0 0 1 3 0V11M14 10.5V6a1.5 1.5 0 0 1 3 0v8c0 4-2.5 7-6.5 7S5 18 4 15l-1-3a1.5 1.5 0 0 1 2.7-1.2L8 13',
  ban: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM5.6 5.6l12.8 12.8',
  table: 'M4 5h16v14H4zM4 10h16M4 15h16M10 5v14',
}
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <path :d="paths[name] || paths.sparkle" />
  </svg>
</template>
