<script setup lang="ts">
import type { TaskStatus } from '../api/contracts.ts'
import { statuses } from '../state/model.ts'
defineProps<{ status: TaskStatus; label?: string | null }>()
</script>
<template><span class="status-label" :class="[status.toLowerCase(), { contradiction: label === '相矛盾', partial: label === '部分支持', insufficient: label === '证据不足' }]">{{ label ?? statuses[status] }}</span></template>
