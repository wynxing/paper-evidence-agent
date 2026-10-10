<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
defineProps<{ title: string; confirmLabel?: string; disabled?: boolean; error?: string }>()
const emit = defineEmits<{ confirm: []; close: [] }>()
const dialog = ref<HTMLDialogElement | null>(null)
onMounted(() => dialog.value?.showModal())
onBeforeUnmount(() => dialog.value?.close())
</script>
<template>
  <dialog ref="dialog" class="confirm-dialog" aria-labelledby="dialog-title" @cancel.prevent="emit('close')">
    <h2 id="dialog-title">{{ title }}</h2>
    <div class="dialog-content"><slot /></div>
    <p v-if="error" class="notice" role="alert">{{ error }}</p>
    <div class="actions"><button type="button" @click="emit('close')">取消</button><button type="button" class="primary" :disabled="disabled" @click="emit('confirm')">{{ confirmLabel ?? '确认' }}</button></div>
  </dialog>
</template>
