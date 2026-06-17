export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: false },
  ssr: false,
  css: ["~/assets/css/main.css"],
  runtimeConfig: {
    public: {
      apiBase:
        process.env.NUXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1.0.0",
    },
  },
  app: {
    head: {
      title: "MMO Dub Studio",
      meta: [
        {
          name: "description",
          content: "Automated video dubbing pipeline — Khmer AI dubbing tool",
        },
        { name: "theme-color", content: "#0a0a0a" },
      ],
      htmlAttrs: { lang: "en" },
      link: [
        // Preconnect for faster font loading
        { rel: "preconnect", href: "https://fonts.googleapis.com" },
        {
          rel: "preconnect",
          href: "https://fonts.gstatic.com",
          crossorigin: "",
        },
        // Material Symbols — required for ALL layouts (editor + default)
        {
          rel: "stylesheet",
          href: "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200",
        },
        // Body fonts
        {
          rel: "stylesheet",
          href: "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap",
        },
      ],
    },
    pageTransition: { name: "page", mode: "out-in" },
  },
  modules: ["@nuxtjs/tailwindcss"],
});
