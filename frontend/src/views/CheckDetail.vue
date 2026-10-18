<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Workbench } from '../state/workbench.ts'
import { anchorWindow, attemptText, detailStopHeading, elapsedText, evidenceContextNotice, evidenceContextSummary, isTerminal, originalClaim, originalDoi, paragraphRole, retrievalFormText, safeSourceUrl, stampText, stages, statuses } from '../state/model.ts'
import StatusBadge from '../components/StatusBadge.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
const { work } = defineProps<{ work: Workbench }>()
const panel = ref(true); const tab = ref('decision'); const deletion = ref(false); const feedback = ref('')
const d = computed(() => work.detail.value)
const terminal = computed(() => d.value && isTerminal(d.value.status))
/** The task record is authoritative; the in-memory submit context only covers the moment right after submitting. */
const claim = computed(() => originalClaim(work.context.value, d.value))
const bibliography = computed(() => d.value?.source ?? work.context.value?.source ?? null)
const doi = computed(() => originalDoi(work.context.value, work.history.value.find(row => row.id === d.value?.id)?.doi, d.value))
const canRetry = computed(() => !!terminal.value && !!doi.value)
const canRevise = computed(() => !!claim.value && !!doi.value)
const queued = computed(() => elapsedText(d.value?.created_at ?? null, d.value?.started_at ?? null))
const ran = computed(() => elapsedText(d.value?.started_at ?? null, d.value?.finished_at ?? null))
const submission = computed(() => work.submittedInput.value?.id === d.value?.id ? work.submittedInput.value : null)
const frozen = computed(() => work.evidenceContext.value?.id === d.value?.id ? work.evidenceContext.value : null)
function opened(event: Event, load: (force?: boolean) => Promise<void>) {
  const target = event.currentTarget
  if (target instanceof HTMLDetailsElement && target.open) void load()
}
function quoteContext(paragraphId: string) {
  const current = frozen.value
  if (!current) return null
  return { notice: evidenceContextNotice(current, paragraphId), ...anchorWindow(current.paragraphs, paragraphId) }
}
</script>
<template>
  <div v-if="d" class="detail-layout" :class="{ 'panel-open': panel }">
    <div class="mobile-tabs" role="tablist" aria-label="核验内容"><button role="tab" :aria-selected="tab === 'decision'" @click="tab = 'decision'">核验意见</button><button role="tab" :aria-selected="tab === 'evidence'" @click="tab = 'evidence'">原文证据</button></div>
    <article class="reading detail-reading" :class="{ 'mobile-hidden': tab !== 'decision' }">
      <div class="section-heading"><p class="eyebrow">核验记录</p><button class="text-button desktop-panel-toggle" :aria-expanded="panel" @click="panel = !panel">{{ panel ? '收起证据' : '查看证据' }}</button></div>
      <h1>核验意见</h1><div class="result-line"><StatusBadge :status="d.status" :label="d.status === 'COMPLETED' ? d.label : null" /><span class="small muted">{{ statuses[d.status] }} · {{ stages[d.stage] }}</span></div>
      <section class="form-section"><h2>论断原句</h2><p class="claim-text">{{ claim || '该任务未记录论断原句。' }}</p>
        <h3>被引文献</h3><template v-if="bibliography"><p>{{ bibliography.title ?? '题名未提供' }}</p><p class="small muted">{{ bibliography.authors.join('、') || '作者未提供' }} · {{ bibliography.year ?? '年份未知' }}</p><p v-if="d.source?.pmcid || d.source?.license" class="small muted">{{ d.source?.pmcid ? `PMC ${d.source.pmcid}` : '' }}<template v-if="d.source?.pmcid && d.source?.license"> · </template>{{ d.source?.license ? `许可 ${d.source.license}` : '' }}</p><p v-if="d.source" class="small muted">取回形态：{{ retrievalFormText(d.source.retrieval_form) }}</p></template><p v-else class="muted">该任务未记录文献信息。</p><p class="mono small muted">{{ doi || 'DOI 暂未提供' }}</p>
      </section>
      <details class="disclosure" @toggle="opened($event, work.loadSubmittedInput)"><summary>原始提交</summary>
        <p v-if="work.submittedInputLoading.value" class="help">正在读取原始提交…</p>
        <template v-if="submission && !work.submittedInputError.value"><dl class="facts"><dt>论断</dt><dd class="claim-text">{{ submission.claim || '提交时未记录论断。' }}</dd><dt>DOI</dt><dd class="mono">{{ submission.doi || '未提供' }}</dd><template v-if="submission.previous_id"><dt>先前任务</dt><dd class="mono">{{ submission.previous_id }}</dd></template><dt>冻结配置摘要</dt><dd class="mono">{{ submission.config_digest || '未提供' }}</dd><dt>授权接收方</dt><dd>{{ submission.authorized_recipients.join('、') || '未记录' }}</dd></dl><p class="help">这是提交时保存的输入，以及创建该任务时冻结的配置摘要。重新核验仍以当前来源预览和运行配置为准。</p></template>
        <template v-else-if="work.submittedInputError.value && !work.submittedInputLoading.value"><p class="help">{{ work.submittedInputError.value }}</p><button class="text-button" @click="work.loadSubmittedInput(true)">重新读取</button></template>
        <p v-else-if="!work.submittedInputLoading.value" class="help">尚未读取。<button class="text-button" @click="work.loadSubmittedInput(true)">读取原始提交</button></p>
      </details>
      <section v-if="!terminal" class="form-section"><h2>{{ d.cancel_requested ? '正在取消' : statuses[d.status] }}</h2><p>当前阶段：{{ stages[d.stage] }}</p><p class="small muted">创建于 {{ stampText(d.created_at) || '未知' }} · 开始于 {{ stampText(d.started_at) || '尚未开始' }}</p><p class="small muted">排队用时：{{ queued }} · 执行用时：{{ ran }}</p><p v-if="d.status === 'QUEUED'" class="help">排队中的任务需要后端 worker 常驻运行才会开始执行，例如 python -m paper_evidence.worker --loop。</p><button :disabled="work.busy.value || d.cancel_requested" @click="work.cancel">取消任务</button><p class="help">取消不保证撤回已发出的请求或费用。</p></section>
      <section v-else-if="d.status !== 'COMPLETED'" class="form-section"><h2>{{ detailStopHeading(d.status, d.error_code, d.source?.retrieval_form) }}</h2><p class="muted">{{ d.status === 'BLOCKED' ? '核验在来源或处理阶段停止，尚未形成学术判断。' : '这是执行状态，不能据此判断文献是否支持论断。' }}</p><p v-if="d.error_code" class="mono small">{{ d.error_code }}</p><p class="small muted">停止阶段：{{ stages[d.stage] }}</p></section>
      <section v-if="d.status === 'COMPLETED' && d.decision" class="form-section decision-section"><h2>{{ d.label === '证据不足' ? '本次未获得足够证据' : 'Paper agent 的核验意见' }}</h2><p>{{ d.decision.rationale }}</p>
        <template v-if="d.decision.supported_parts.length"><h3>支持的部分</h3><ul><li v-for="(part, i) in d.decision.supported_parts" :key="i">{{ part }}</li></ul></template>
        <template v-if="d.decision.scope_differences.length"><h3>范围差异</h3><ul><li v-for="(part, i) in d.decision.scope_differences" :key="i">{{ part }}</li></ul></template>
        <template v-if="d.decision.limitations.length"><h3>限制</h3><ul><li v-for="(part, i) in d.decision.limitations" :key="i">{{ part }}</li></ul></template>
        <p class="help">该意见仅针对指定文献与当前论断的关系，模型标签不等于客观真值。</p>
      </section>
      <details class="disclosure"><summary>调用账与运行信息</summary><dl class="facts"><dt>主请求</dt><dd>{{ d.accounting.main_requests_used }} / {{ d.limits.main_requests }}</dd><dt>输出修复</dt><dd>{{ d.accounting.repair_requests_used }} / {{ d.limits.repair_requests }}</dd><dt>上游尝试</dt><dd>{{ attemptText(d.accounting) }} / 上限 {{ (d.limits.main_requests + d.limits.repair_requests) * d.limits.attempts_per_request }}</dd><dt>费用</dt><dd>未知</dd><dt>创建时间</dt><dd>{{ stampText(d.created_at) || '未知' }}</dd><dt>开始时间</dt><dd>{{ stampText(d.started_at) || '尚未开始' }}</dd><dt>结束时间</dt><dd>{{ stampText(d.finished_at) || '尚未结束' }}</dd><dt>排队 / 执行用时</dt><dd>{{ queued }} / {{ ran }}</dd><dt>任务标识</dt><dd class="mono">{{ d.id }}</dd></dl></details>
      <div class="task-actions"><button :disabled="work.busy.value || !canRetry" @click="work.prepareEdit(false, true)">重新授权并重试</button><button :disabled="work.busy.value || !canRevise" @click="work.prepareEdit()">修改原句</button><button :disabled="work.busy.value || !canRevise" @click="work.prepareEdit(true)">拆分论断</button></div>
      <p v-if="!doi" class="help">无法读取原任务 DOI，请刷新本地历史后再重新核验。</p>
      <p v-else-if="!claim" class="help">该任务未记录论断原句，修改与拆分暂不可用；重试由后端使用原任务输入。</p>
      <section class="form-section"><label for="feedback">留下意见 <span class="muted">可选</span></label><textarea id="feedback" v-model="feedback" rows="2" placeholder="记录你对本次核验的意见。" /><div class="feedback-actions"><button :disabled="!feedback.trim() || work.busy.value" @click="work.feedback(feedback)">保存意见</button><button class="text-button danger" :disabled="!terminal || work.busy.value" @click="deletion = true">删除本地记录</button></div></section>
    </article>
    <aside class="evidence-panel" :class="{ 'desktop-hidden': !panel, 'mobile-hidden': tab !== 'evidence' }" aria-labelledby="evidence-heading"><div class="section-heading"><h2 id="evidence-heading">原文证据</h2><span class="small muted">{{ d.decision?.evidence.length ?? 0 }} 条</span></div><p class="help">摘录与原文位置。展开可查看冻结段落；邻段只作上下文，不是证据。</p>
      <details class="disclosure" @toggle="opened($event, work.loadEvidenceContext)"><summary>查看冻结上下文</summary>
        <p v-if="work.evidenceContextLoading.value" class="help">正在读取邻段…</p>
        <template v-if="frozen && !work.evidenceContextError.value"><p v-if="evidenceContextSummary(frozen)" class="help">{{ evidenceContextSummary(frozen) }}</p><p v-else class="help">{{ frozen.paragraphs.length }} 段，按段落顺序排列。没有「被引用」或「进入模型上下文」标记的是邻段。</p><section v-for="(paragraph, index) in frozen.paragraphs" :key="`${paragraph.paragraph_id}-${index}`" class="context-block"><p class="context-role">{{ paragraphRole(paragraph) }} · {{ paragraph.section || '章节未提供' }}</p><p v-if="paragraph.text">{{ paragraph.text }}</p><p v-else class="help">该段没有可显示的文本。</p><p class="mono small muted">{{ paragraph.paragraph_id }}</p></section></template>
        <template v-else-if="work.evidenceContextError.value && !work.evidenceContextLoading.value"><p class="help">{{ work.evidenceContextError.value }}</p><button class="text-button" @click="work.loadEvidenceContext(true)">重新读取</button></template>
        <p v-else-if="!work.evidenceContextLoading.value" class="help">尚未读取。<button class="text-button" @click="work.loadEvidenceContext(true)">读取冻结上下文</button></p>
      </details>
      <p v-if="!d.decision?.evidence.length" class="empty">{{ d.status === 'COMPLETED' ? '本次没有可展示的证据摘录。' : '尚无通过校验的最终证据。' }}</p>
      <section v-for="(e, i) in d.decision?.evidence ?? []" :key="e.paragraph_id" class="evidence-item"><div class="evidence-meta"><span class="evidence-number">{{ i + 1 }}</span><span>{{ e.section }}</span></div><blockquote>{{ e.quote }}</blockquote><p class="mono small muted">{{ e.paragraph_id }}</p><a v-if="safeSourceUrl(e.source_url)" :href="safeSourceUrl(e.source_url)!" target="_blank" rel="noopener noreferrer">打开来源 ↗</a><p v-else class="small muted">{{ work.demo ? '构造摘录，无真实来源链接' : '未提供可用的来源链接' }}</p>
        <details @toggle="opened($event, work.loadEvidenceContext)"><summary class="small muted">查看邻段</summary>
          <p v-if="work.evidenceContextLoading.value" class="help">正在读取邻段…</p>
          <template v-if="frozen && !work.evidenceContextError.value"><template v-for="item in [quoteContext(e.paragraph_id)]" :key="e.paragraph_id"><p v-if="item?.notice" class="help">{{ item.notice }}</p><div v-if="item?.before" class="context-block"><p class="context-role">{{ paragraphRole(item.before) }} · {{ item.before.section || '章节未提供' }}</p><p v-if="item.before.text">{{ item.before.text }}</p><p v-else class="help">该段没有可显示的文本。</p></div><div v-if="item?.anchor" class="context-block"><p class="context-role">冻结段落 · {{ item.anchor.section || '章节未提供' }}</p><p v-if="item.anchor.text">{{ item.anchor.text }}</p><p v-else class="help">该段没有可显示的文本。</p></div><div v-if="item?.after" class="context-block"><p class="context-role">{{ paragraphRole(item.after) }} · {{ item.after.section || '章节未提供' }}</p><p v-if="item.after.text">{{ item.after.text }}</p><p v-else class="help">该段没有可显示的文本。</p></div></template></template>
          <template v-else-if="work.evidenceContextError.value && !work.evidenceContextLoading.value"><p class="help">{{ work.evidenceContextError.value }}</p><button class="text-button" @click="work.loadEvidenceContext(true)">重新读取</button></template>
          <p v-else-if="!work.evidenceContextLoading.value" class="help">尚未读取。<button class="text-button" @click="work.loadEvidenceContext(true)">读取邻段</button></p>
        </details>
        <details><summary class="small muted">段落校验标识</summary><p class="mono small">{{ e.paragraph_hash }}</p></details></section>
    </aside>
    <ConfirmDialog v-if="deletion" title="删除本地记录？" confirm-label="删除记录" @close="deletion = false" @confirm="deletion = false; work.remove()"><p>仅删除本地任务及关联记录，不能撤回已发生的云模型调用或删除上游可能保留的数据。</p></ConfirmDialog>
  </div>
</template>
