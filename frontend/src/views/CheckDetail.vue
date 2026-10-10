<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Workbench } from '../state/workbench.ts'
import { attemptText, errors, isTerminal, safeSourceUrl, stages, statuses } from '../state/model.ts'
import StatusBadge from '../components/StatusBadge.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
const { work } = defineProps<{ work: Workbench }>()
const panel = ref(true); const tab = ref('decision'); const deletion = ref(false); const feedback = ref('')
const d = computed(() => work.detail.value)
const terminal = computed(() => d.value && isTerminal(d.value.status))
const doi = computed(() => work.context.value?.doi || work.history.value.find(row => row.id === d.value?.id)?.doi || '')
const canRetry = computed(() => !!terminal.value && !!doi.value)
const canRevise = computed(() => !!work.context.value?.claim && !!doi.value)
</script>
<template>
  <div v-if="d" class="detail-layout" :class="{ 'panel-open': panel }">
    <div class="mobile-tabs" role="tablist" aria-label="核验内容"><button role="tab" :aria-selected="tab === 'decision'" @click="tab = 'decision'">核验意见</button><button role="tab" :aria-selected="tab === 'evidence'" @click="tab = 'evidence'">原文证据</button></div>
    <article class="reading detail-reading" :class="{ 'mobile-hidden': tab !== 'decision' }">
      <div class="section-heading"><p class="eyebrow">核验记录</p><button class="text-button desktop-panel-toggle" :aria-expanded="panel" @click="panel = !panel">{{ panel ? '收起证据' : '查看证据' }}</button></div>
      <h1>核验意见</h1><div class="result-line"><StatusBadge :status="d.status" :label="d.status === 'COMPLETED' ? d.label : null" /><span class="small muted">{{ statuses[d.status] }} · {{ stages[d.stage] }}</span></div>
      <section class="form-section"><h2>论断原句</h2><p class="claim-text">{{ work.context.value?.claim ?? '当前接口未提供原始论断。刷新页面后，本次输入上下文无法恢复。' }}</p>
        <h3>被引文献</h3><template v-if="work.context.value?.source"><p>{{ work.context.value.source.title }}</p><p class="small muted">{{ work.context.value.source.authors.join('、') }} · {{ work.context.value.source.year ?? '年份未知' }}</p></template><p v-else class="muted">当前接口未提供完整文献信息。</p><p class="mono small muted">{{ work.context.value?.doi ?? work.history.value.find(x => x.id === d!.id)?.doi ?? 'DOI 暂未提供' }}</p>
      </section>
      <section v-if="!terminal" class="form-section"><h2>{{ d.cancel_requested ? '正在取消' : statuses[d.status] }}</h2><p>当前阶段：{{ stages[d.stage] }}</p><p class="small muted">排队时长：暂无数据 · 执行用时：暂无数据</p><button :disabled="work.busy.value || d.cancel_requested" @click="work.cancel">取消任务</button><p class="help">取消不保证撤回已发出的请求或费用。</p></section>
      <section v-else-if="d.status !== 'COMPLETED'" class="form-section"><h2>{{ d.error_code ? errors[d.error_code] : statuses[d.status] }}</h2><p class="muted">{{ d.status === 'BLOCKED' ? '核验在来源或处理阶段停止，尚未形成学术判断。' : '这是执行状态，不能据此判断文献是否支持论断。' }}</p><p v-if="d.error_code" class="mono small">{{ d.error_code }}</p><p class="small muted">停止阶段：{{ stages[d.stage] }}</p></section>
      <section v-if="d.status === 'COMPLETED' && d.decision" class="form-section decision-section"><h2>{{ d.label === '证据不足' ? '本次未获得足够证据' : 'Paper agent 的核验意见' }}</h2><p>{{ d.decision.rationale }}</p>
        <template v-if="d.decision.supported_parts.length"><h3>支持的部分</h3><ul><li v-for="(part, i) in d.decision.supported_parts" :key="i">{{ part }}</li></ul></template>
        <template v-if="d.decision.scope_differences.length"><h3>范围差异</h3><ul><li v-for="(part, i) in d.decision.scope_differences" :key="i">{{ part }}</li></ul></template>
        <template v-if="d.decision.limitations.length"><h3>限制</h3><ul><li v-for="(part, i) in d.decision.limitations" :key="i">{{ part }}</li></ul></template>
        <p class="help">该意见仅针对指定文献与当前论断的关系，模型标签不等于客观真值。</p>
      </section>
      <details class="disclosure"><summary>调用账与运行信息</summary><dl class="facts"><dt>主请求</dt><dd>{{ d.accounting.main_requests_used }} / {{ d.limits.main_requests }}</dd><dt>输出修复</dt><dd>{{ d.accounting.repair_requests_used }} / {{ d.limits.repair_requests }}</dd><dt>上游尝试</dt><dd>{{ attemptText(d.accounting) }} / 上限 {{ (d.limits.main_requests + d.limits.repair_requests) * d.limits.attempts_per_request }}</dd><dt>费用</dt><dd>未知</dd><dt>排队 / 执行用时</dt><dd>暂无数据</dd><dt>任务标识</dt><dd class="mono">{{ d.id }}</dd></dl></details>
      <div class="task-actions"><button :disabled="work.busy.value || !canRetry" @click="work.prepareEdit(false, true)">重新授权并重试</button><button :disabled="work.busy.value || !canRevise" @click="work.prepareEdit()">修改原句</button><button :disabled="work.busy.value || !canRevise" @click="work.prepareEdit(true)">拆分论断</button></div>
      <p v-if="!doi" class="help">无法读取原任务 DOI，请刷新本地历史后再重新核验。</p>
      <p v-else-if="!work.context.value?.claim" class="help">原句不可读取，修改与拆分暂不可用；重试由后端使用原任务输入。</p>
      <section class="form-section"><label for="feedback">留下意见 <span class="muted">可选</span></label><textarea id="feedback" v-model="feedback" rows="2" placeholder="记录你对本次核验的意见。" /><div class="feedback-actions"><button :disabled="!feedback.trim() || work.busy.value" @click="work.feedback(feedback)">保存意见</button><button class="text-button danger" :disabled="!terminal || work.busy.value" @click="deletion = true">删除本地记录</button></div></section>
    </article>
    <aside class="evidence-panel" :class="{ 'desktop-hidden': !panel, 'mobile-hidden': tab !== 'evidence' }" aria-labelledby="evidence-heading"><div class="section-heading"><h2 id="evidence-heading">原文证据</h2><span class="small muted">{{ d.decision?.evidence.length ?? 0 }} 条</span></div><p class="help">摘录与原文位置。相邻上下文当前接口未提供。</p>
      <p v-if="!d.decision?.evidence.length" class="empty">{{ d.status === 'COMPLETED' ? '本次没有可展示的证据摘录。' : '尚无通过校验的最终证据。' }}</p>
      <section v-for="(e, i) in d.decision?.evidence ?? []" :key="e.paragraph_id" class="evidence-item"><div class="evidence-meta"><span class="evidence-number">{{ i + 1 }}</span><span>{{ e.section }}</span></div><blockquote>{{ e.quote }}</blockquote><p class="mono small muted">{{ e.paragraph_id }}</p><a v-if="safeSourceUrl(e.source_url)" :href="safeSourceUrl(e.source_url)!" target="_blank" rel="noopener noreferrer">打开来源 ↗</a><p v-else class="small muted">{{ work.demo ? '构造摘录，无真实来源链接' : '未提供可用的来源链接' }}</p><details><summary class="small muted">段落校验标识</summary><p class="mono small">{{ e.paragraph_hash }}</p></details></section>
    </aside>
    <ConfirmDialog v-if="deletion" title="删除本地记录？" confirm-label="删除记录" @close="deletion = false" @confirm="deletion = false; work.remove()"><p>仅删除本地任务及关联记录，不能撤回已发生的云模型调用或删除上游可能保留的数据。</p></ConfirmDialog>
  </div>
</template>
