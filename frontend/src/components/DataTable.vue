<template>
  <el-table
    :data="rows"
    stripe
    :height="height"
    :row-key="rowKey"
    size="small"
    :default-sort="defSort"
    :empty-text="emptyText"
    style="width: 100%"
  >
    <el-table-column v-if="showIndex" type="index" label="#" width="52" align="center" fixed />
    <el-table-column
      v-for="c in columns"
      :key="c.prop"
      :prop="c.prop"
      :label="c.label"
      :width="c.width"
      :min-width="c.minWidth"
      :align="c.align || 'left'"
      :sortable="c.sortable"
      :fixed="c.fixed"
    >
      <template #default="scope">
        <span :class="c.cellClass ? c.cellClass(scope.row) : ''">{{ display(scope.row, c) }}</span>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup>
defineProps({
  rows: { type: Array, default: () => [] },
  columns: { type: Array, required: true },
  rowKey: { type: String, default: 'code' },
  showIndex: { type: Boolean, default: true },
  height: { type: String, default: '540px' },
  defSort: { type: Object, default: null },
  emptyText: { type: String, default: '加载中...' }
})

function display(row, c) {
  if (c.render) return c.render(row)
  if (c.formatter) return c.formatter(row)
  const v = row[c.prop]
  return v === null || v === undefined ? '--' : v
}
</script>
