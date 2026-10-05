<script setup lang="ts">
import { computed } from 'vue'
import type { Workbench } from '../state/workbench.ts'
import { canSubmit, validDoi } from '../state/model.ts'
import { demoScenarios, type DemoScenario } from '../api/demo.ts'
const { work } = defineProps<{ work: Workbench }>()
const ready = computed(() => canSubmit(work.draft) && !work.busy.value)
const value = (e: Event) => (e.target as HTMLInputElement).value
</script>
<template>
  <section class="reading new-check" aria-labelledby="new-heading">
    <p class="eyebrow">单条论断 · 指定文献</p><h1 id="new-heading">新的核验</h1>
    <p class="lead">这条论断，是否得到了被引文献的支持？</p>
    <p v-if="work.draft.previousId" class="notice">关联原任务 {{ work.draft.previousId }}。提交将创建新任务，保留原记录。</p>
    <form @submit.prevent="work.submit">
      <div class="form-section">
        <label for="claim">论断原句 <span class="muted">{{ work.draft.retryId ? '后端将使用原任务输入' : '中文或英文' }}</span></label>
        <textarea id="claim" :value="work.draft.claim" :disabled="!!work.draft.retryId || work.busy.value" rows="5" placeholder="粘贴一条需要复查的论断，保留对象、条件与结论范围。" @input="work.changeClaim(value($event))" />
        <p class="help">一次核验一个可独立判断的主张。多个主张请手动拆分，分别提交。</p>
        <label for="doi">被引文献 DOI</label>
        <div class="input-action"><input id="doi" :value="work.draft.doi" :disabled="!!work.draft.retryId || work.busy.value" placeholder="10.xxxx/文献标识" @input="work.changeDoi(value($event))" /><button type="button" :disabled="!validDoi(work.draft.doi) || work.resolving.value || work.busy.value" @click="work.resolve">{{ work.resolving.value ? '正在读取…' : '读取文献' }}</button></div>
      </div>
      <section v-if="work.draft.source" class="form-section source-preview" aria-labelledby="source-heading">
        <p class="eyebrow" id="source-heading">文献身份</p><h2>{{ work.draft.source.title }}</h2>
        <p class="muted">{{ work.draft.source.authors.join('、') || '作者信息未提供' }} · {{ work.draft.source.year ?? '年份未知' }}</p><p class="mono muted">{{ work.draft.source.doi }}</p>
        <label class="checkbox"><input v-model="work.draft.sourceConfirmed" type="checkbox" :disabled="work.busy.value" @change="work.draft.cloudConsent = false" />我确认这是拟引用的文献</label>
      </section>
      <section v-if="work.draft.config" class="form-section" aria-labelledby="consent-heading">
        <h2 id="consent-heading">本次调用授权</h2><p class="muted">整次任务将发送以下数据；授权覆盖查询生成、判断、补充检索及输出修复。</p>
        <dl class="facts"><dt>数据范围</dt><dd>{{ work.draft.config.data_scope.join('、') }}</dd><dt>主接收方</dt><dd>{{ work.draft.config.primary_recipient }}</dd><dt>模型别名</dt><dd>{{ work.draft.config.model_alias }}</dd><dt>调用上限</dt><dd>{{ work.draft.config.limits.main_requests + work.draft.config.limits.repair_requests }} 个逻辑请求 / {{ (work.draft.config.limits.main_requests + work.draft.config.limits.repair_requests) * work.draft.config.limits.attempts_per_request }} 次上游尝试</dd><dt>执行时限</dt><dd>任务 {{ work.draft.config.timeouts.task_seconds }} 秒，不含排队；单次模型 {{ work.draft.config.timeouts.model_attempt_seconds }} 秒；来源请求 {{ work.draft.config.timeouts.source_request_seconds }} 秒</dd><dt>观测导出</dt><dd>{{ work.draft.config.observability.langfuse_enabled ? `已配置：${work.draft.config.observability.recipient ?? '接收方未知'}` : '关闭，仅使用本地轨迹' }}</dd></dl>
        <div v-if="work.draft.config.fallback_recipients.length" class="fallbacks"><p class="small muted">可选备用接收方，仅选中者可收到数据。</p><label v-for="recipient in work.draft.config.fallback_recipients" :key="recipient" class="checkbox"><input v-model="work.draft.fallbacks" type="checkbox" :value="recipient" :disabled="work.busy.value" @change="work.draft.cloudConsent = false" />{{ recipient }}</label></div>
        <p class="help">Token 和费用无法可靠预估；调用次数不是费用上限。模型调用授权不包含语义诊断包外传。</p>
        <label class="checkbox"><input v-model="work.draft.cloudConsent" type="checkbox" :disabled="!work.draft.sourceConfirmed || work.busy.value" />我同意本次任务向以上接收方发送所列数据</label>
      </section>
      <div v-if="work.demo" class="form-section demo-choice"><label for="scenario">模拟结果场景</label><select id="scenario" :value="work.scenario.value" @change="work.selectScenario(value($event) as DemoScenario)"><option v-for="s in demoScenarios" :key="s">{{ s }}</option></select><p class="help">文献、摘录与结果均为构造数据，不访问来源或模型。</p></div>
      <div class="submit-row"><p class="small muted">{{ work.draft.cloudConsent ? '授权仅用于本次任务。' : '未授权不会创建任务。草稿仅在本页内存保存。' }}</p><button class="primary" type="submit" :disabled="!ready">{{ work.busy.value ? '提交中…' : work.draft.retryId ? '重新授权并重试' : '开始核验' }}</button></div>
    </form>
  </section>
</template>
