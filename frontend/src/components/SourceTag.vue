<template>
  <el-tag v-if="demo" type="warning" size="small" effect="plain">示例数据</el-tag>
  <el-tag v-else type="success" size="small" effect="plain">实时数据</el-tag>
</template>

<script setup>
import { computed } from 'vue'
import { isDemo } from '../api'

const props = defineProps({
  section: { type: String, required: true }
})
const demo = computed(() => isDemo(props.section))
</script>
