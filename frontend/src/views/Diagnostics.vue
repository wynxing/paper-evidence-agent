<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Workbench } from '../state/workbench.ts'
import { attemptText, errors, stages } from '../state/model.ts'
import { downloadPacket, projectPacket } from '../api/export.ts'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import StatusBadge from '../components/StatusBadge.vue'
const { work } = defineProps<{ work: Workbench }>()
const p = computed(() => work.packet.value); const exporting = ref(false); const recipient = ref(''); const consent = ref(false)
const json = computed(() => p.value ? JSON.stringify(projectPacket(p.value), null, 2) : '')
async function exportSemantic() { const data = await work.semanticExport(recipient.value); if (data) { downloadPacket(data); exporting.value = false; work.message.value = '诊断包下载已发起，未自动发送给接收方。请检查浏览器下载结果。' } }
</script>
<template>
  <section class="diagnostics reading" aria-labelledby="diagnostic-heading">
    <button class="text-button back-link" @click="work.navigate(work.route.value.id!)">← 返回核验意见</button><p class="eyebrow">执行记录 · 诊断包</p><h1 id="diagnostic-heading">运行诊断</h1><p class="lead">查看任务实际执行的步骤、调用与停止原因。</p>
    <div v-if="!p" class="empty"><p>诊断包尚未读取成功。</p><button :disabled="work.busy.value" @click="work.refreshPacket()">重新读取诊断包</button></div>
    <template v-else>
      <div class="result-line"><StatusBadge :status="p.status" /><span class="small muted">schema {{ p.schema_version }} · {{ p.input.privacy }}</span></div>
      <dl class="facts diagnostics-facts"><dt>任务</dt><dd class="mono">{{ p.case_id }}</dd><dt>运行 / 轨迹</dt><dd class="mono">{{ p.run_id }} / {{ p.trace_id }}</dd><dt>停止原因</dt><dd>{{ p.error_code ? errors[p.error_code] ?? p.error_code : '无已记录错误' }}</dd><dt>主请求 / 修复</dt><dd>{{ p.accounting.main_requests_used }} / {{ p.run_config.limits.main_requests }} · {{ p.accounting.repair_requests_used }} / {{ p.run_config.limits.repair_requests }}</dd><dt>上游尝试</dt><dd>{{ attemptText(p.accounting) }}</dd><dt>判据版本</dt><dd>{{ p.criteria.version }} <span class="mono muted">{{ p.criteria.digest }}</span></dd><dt>配置 / 实现</dt><dd class="mono">{{ p.run_config.config_digest }} / {{ p.criteria.implementation_revision }}</dd></dl>
      <section class="form-section"><div class="section-heading"><h2>执行时间线</h2><button class="text-button" @click="work.refreshPacket()">刷新记录</button></div><p class="help">可观察的执行记录，不代表模型完整思考过程。</p><p v-if="!p.execution.length" class="empty">当前没有执行记录。</p><ol class="timeline"><li v-for="(step, i) in p.execution" :key="`${step.span_id}-${i}`"><span class="timeline-dot" :class="step.status" aria-hidden="true"></span><details><summary><span>{{ stages[step.stage] ?? step.stage }}</span><span class="small muted">{{ { success: '成功', error: '错误', blocked: '阻断', cancelled: '取消' }[step.status] }} · {{ step.duration_ms === null ? '耗时未知' : `${step.duration_ms} ms` }}</span></summary><dl class="facts"><dt>工具</dt><dd>{{ step.tool }}</dd><dt>Span</dt><dd class="mono">{{ step.span_id }}</dd><dt>请求关联</dt><dd class="mono">{{ step.request_id ?? '无' }}</dd><dt>轮次</dt><dd>{{ step.round ?? '不适用' }}</dd><dt>错误</dt><dd>{{ step.error_code ?? '无' }}</dd></dl></details></li></ol></section>
      <section class="form-section"><h2>模型请求与逐次尝试</h2><p v-if="!p.model_calls.length" class="empty">当前没有已记录的模型请求。</p><details v-for="call in p.model_calls" :key="call.request_id" class="disclosure"><summary>{{ stages[call.purpose] ?? call.purpose }} <span class="mono small muted">{{ call.request_id }}</span></summary><p class="small">候选段落：{{ call.context_paragraph_ids.join('、') || '无' }}</p><div class="table-scroll"><table><caption class="sr-only">请求 {{ call.request_id }} 的上游尝试</caption><thead><tr><th>尝试</th><th>状态</th><th>恢复</th><th>模型版本</th><th>Tokens</th></tr></thead><tbody><tr v-for="a in call.attempts" :key="a.attempt_id"><td>{{ a.attempt_index }}<br /><span class="mono small muted">{{ a.attempt_id }}</span></td><td>{{ { success: '成功', error: '错误', cancelled: '取消' }[a.status] }}<br /><span class="small muted">{{ a.error_code ?? '无错误' }}</span></td><td>{{ { none: '无', retry: '重试', fallback: '备用路由' }[a.recovery_kind] }}</td><td>{{ a.verified_model_version ?? '未知' }}</td><td>{{ a.usage?.total_tokens ?? '未知' }}</td></tr></tbody></table></div><p class="small muted">模型别名：{{ call.model_alias }} · 提示词版本：{{ call.prompt_version }}</p></details></section>
      <section class="form-section"><h2>诊断包</h2><p class="notice">书目字段未遮盖，可识别文献及相关主题。脱敏包隐藏论断与生成文本，不能用于声称复现全部语义缺陷。</p><div class="actions"><button @click="downloadPacket(p)">下载脱敏包</button><button :disabled="work.busy.value" @click="exporting = true; consent = false">预览语义导出范围</button></div><details class="disclosure"><summary>查看脱敏 JSON</summary><pre class="json-preview">{{ json }}</pre></details></section>
    </template>
    <ConfirmDialog v-if="exporting" title="语义诊断包导出" confirm-label="授权并下载到本地" :disabled="!consent || !recipient.trim() || work.busy.value" @close="exporting = false" @confirm="exportSemantic">
      <p>拟导出：论断原句、获许可的证据片段、判断文本，以及脱敏包中的执行和版本字段。实际生成范围由后端校验来源许可。</p><p class="help">不包含完整提示词、原始模型响应或密钥。下载后由你决定是否交给接收方；本应用不会自动上传。</p><label for="recipient">拟接收方</label><input id="recipient" v-model="recipient" placeholder="填写评审人员或外部 Agent 名称" /><label class="checkbox"><input v-model="consent" type="checkbox" />我同意为所列接收方导出上述语义数据</label>
    </ConfirmDialog>
  </section>
</template>
