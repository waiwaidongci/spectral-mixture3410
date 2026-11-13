<script setup lang="ts">
import {ref,watch} from 'vue';
import {Library,RealignResult} from '../types/domain';
import {updateInterpolationGap,GapUpdateResult} from '../api/libraries';
import {realignLibrarySamples} from '../api/samples';
import {useAction} from '../hooks/useAction';
const props=defineProps<{library:Library;canEdit:boolean;pointwiseCount:number}>();
const emit=defineEmits<{changed:[]}>();
const a=useAction();
const gap=ref<number>(props.library.max_interp_gap);
const summary=ref('');
watch(()=>props.library.id,()=>{gap.value=props.library.max_interp_gap;summary.value='';});
async function saveGap(){
  await a.execute(async()=>{
    const r:GapUpdateResult=await updateInterpolationGap(props.library.id,gap.value);
    summary.value=`跨度已更新；${r.pointwise_samples_pending_realignment} 个逐点样本需从原始谱重算后，新研究才采用新读数。既有研究与获批导出保持原对齐结果。`;
    emit('changed');
  });
}
async function realignAll(){
  await a.execute(async()=>{
    const r:RealignResult=await realignLibrarySamples(props.library.id);
    summary.value=`已从原始谱重算 ${r.realigned.length} 个样本（规则 ${r.rule_version}，跨度上限 ${r.max_interp_gap}nm）。再建研究即使用新读数。`;
    emit('changed');
  });
}
</script>
<template>
  <section v-if="canEdit" class="gap-panel">
    <div class="section-heading"><h2>对齐规则与重算</h2><span>逐点谱按本库波长网格线性插值 · 禁止外推</span></div>
    <div v-if="a.error.value" class="notice" role="alert">{{a.error.value}}</div>
    <form class="gap-form" @submit.prevent="saveGap">
      <label>相邻测点最大插值跨度（nm，5–200）
        <input aria-label="相邻测点最大插值跨度" type="number" min="5" max="200" step="1" v-model.number="gap" required/>
      </label>
      <button class="outline" :disabled="a.busy.value">保存规则</button>
      <button class="outline" type="button" :disabled="a.busy.value||pointwiseCount===0" @click="realignAll">
        从原始谱批量重算（{{pointwiseCount}}）
      </button>
    </form>
    <p v-if="summary" class="caption gap-summary">{{summary}}</p>
  </section>
</template>
