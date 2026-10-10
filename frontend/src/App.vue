<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useWorkbench } from './state/workbench.ts'
import NewCheck from './views/NewCheck.vue'
import CheckDetail from './views/CheckDetail.vue'
import Diagnostics from './views/Diagnostics.vue'
import StatusBadge from './components/StatusBadge.vue'
import { statuses } from './state/model.ts'
const work = useWorkbench(); const sidebar = ref(window.innerWidth >= 768)
const narrow = ref(window.innerWidth < 768)
const navElement = ref<HTMLElement | null>(null); const navToggle = ref<HTMLButtonElement | null>(null)
const media = window.matchMedia('(max-width: 767px)')
function resized() { narrow.value = media.matches; sidebar.value = !media.matches }
function drawerKeys(event: KeyboardEvent) {
  if (!narrow.value || !sidebar.value) return
  if (event.key === 'Escape') { sidebar.value = false; return }
  if (event.key !== 'Tab') return
  const controls = [...(navElement.value?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)') ?? [])]
  if (!controls.length) return
  const first = controls[0]!; const last = controls[controls.length - 1]!
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
}
watch(sidebar, async value => { if (!narrow.value) return; await nextTick(); if (value) navElement.value?.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus(); else navToggle.value?.focus() })
onMounted(() => media.addEventListener('change', resized))
onUnmounted(() => media.removeEventListener('change', resized))
const title = computed(() => ({ new: '新的核验', check: '核验意见', diagnostic: '运行诊断' })[work.route.value.view])
watch(work.route, () => { if (window.innerWidth < 768) sidebar.value = false })
</script>
<template>
  <div class="workbench" :class="{ 'sidebar-collapsed': !sidebar }">
    <a class="skip-link" href="#main-content" @click.prevent="($refs.main as HTMLElement).focus()">跳到主要内容</a>
    <button v-if="sidebar" class="sidebar-backdrop" aria-label="关闭导航" @click="sidebar = false"></button>
    <aside ref="navElement" class="sidebar" aria-label="工作台导航" :inert="!sidebar" @keydown="drawerKeys">
      <div class="brand"><span class="brand-mark" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M6 3h9l3 3v15H6zM15 3v4h4M9 11h6M9 15h6" /></svg></span><span>Paper Evidence<small>引文核验工作台</small></span></div>
      <button v-if="narrow" class="text-button" @click="sidebar = false">收起导航</button>
      <button class="nav-new" :class="{ active: work.route.value.view === 'new' }" :disabled="work.busy.value" @click="work.startNew"><span aria-hidden="true">＋</span> 新的核验</button>
      <div class="history-label"><span>本地历史</span><button class="icon-button" aria-label="刷新本地历史" @click="work.refreshHistory">↻</button></div>
      <p v-if="work.historyError.value" class="sidebar-notice">{{ work.historyError.value }}</p><p v-else-if="!work.history.value.length" class="sidebar-notice">暂无核验记录</p>
      <nav class="history-list"><button v-for="row in work.history.value" :key="row.id" :class="{ active: row.id === work.route.value.id }" :aria-current="row.id === work.route.value.id ? 'page' : undefined" :disabled="work.busy.value" @click="work.navigate(row.id)"><span class="history-doi">{{ row.doi }}</span><span class="history-state"><StatusBadge :status="row.status" :label="row.label" /><span v-if="row.label" class="small muted">{{ statuses[row.status] }}</span></span></button></nav>
      <div class="sidebar-footer"><span class="local-dot" aria-hidden="true"></span> {{ work.demo ? '模拟数据 · 仅本页内存' : '本机工作空间' }}<p>单条论断，逐条核对。</p></div>
    </aside>
    <div class="main-shell" :inert="narrow && sidebar"><header class="toolbar">
      <div class="toolbar-path"><button ref="navToggle" class="icon-button" :aria-expanded="sidebar" aria-label="切换导航" @click="sidebar = !sidebar"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M9 4v16" /></svg></button><span class="muted">工作空间</span><span class="separator">/</span><span>{{ title }}</span></div>
      <div class="toolbar-actions">
        <span class="mode-label" :class="{ demo: work.demo }">{{ work.demo ? '模拟演示 · 构造数据' : '真实接口模式' }}</span>
        <button v-if="work.route.value.view === 'check' && work.route.value.id" :disabled="work.busy.value" @click="work.navigate(work.route.value.id, true)">运行诊断</button>
      </div>
    </header>
      <main id="main-content" ref="main" tabindex="-1">
        <div v-if="work.message.value" class="page-notice" role="status">{{ work.message.value }}<button class="icon-button" aria-label="关闭提示" @click="work.message.value = ''">×</button></div>
        <div v-if="work.connectionError.value" class="page-notice" role="status">{{ work.connectionError.value }}<button @click="work.reload">重新读取</button></div>
        <div v-if="work.loading.value" class="reading empty" role="status">正在读取任务…</div>
        <NewCheck v-else-if="work.route.value.view === 'new'" :work="work" />
        <Diagnostics v-else-if="work.route.value.view === 'diagnostic'" :key="`diagnostic-${work.route.value.id}`" :work="work" />
        <CheckDetail v-else-if="work.detail.value" :key="work.route.value.id!" :work="work" />
        <div v-else class="reading empty"><h1>任务暂不可读取</h1><p>检查接口连接或任务标识后重新读取。</p><button @click="work.reload">重新读取</button></div>
      </main>
    </div>
  </div>
</template>
