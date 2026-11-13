<script setup lang="ts">
import {computed,ref} from 'vue';
import {Library,Sample} from '../types/domain';
import {importPointwiseSpectrum,realignSample} from '../api/samples';
import {useAction} from '../hooks/useAction';
import {toPointwiseInput} from '../utils/pointwise';
const props=defineProps<{sample:Sample;library:Library;canEdit:boolean}>();
const emit=defineEmits<{saved:[]}>();
const a=useAction();
const open=ref(false);
const text=ref('');
const overrideGap=ref<number|''|null>(null);
const hasRaw=computed(()=>!!props.sample.raw_wavelengths);
const spanHint=computed(()=>`库网格 ${props.library.wavelengths[0]}–${props.library.wavelengths[props.library.wavelengths.length-1]}nm，当前相邻测点跨度上限 ${props.library.max_interp_gap}nm`);
async function submit(){
  await a.execute(async()=>{
    const body=toPointwiseInput(text.value,overrideGap.value);
    await importPointwiseSpectrum(props.sample.id,body);
    text.value='';overrideGap.value=null;open.value=false;emit('saved');
  });
}
async function realign(){
  await a.execute(async()=>realignSample(props.sample.id).then(()=>emit('saved')));
}
</script>
<template>
  <div class="pointwise">
    <div class="pointwise-actions">
      <button v-if="canEdit" class="text-link" @click="open=!open">{{hasRaw?'重新导入逐点谱':'导入逐点测谱'}}</button>
      <button v-if="canEdit&&hasRaw" class="text-link" @click="realign">按当前规则重算</button>
      <span v-if="hasRaw" class="align-badge">已逐点对齐 · {{sample.alignment_rule}}</span>
    </div>
    <div v-if="a.error.value" class="notice" role="alert">{{a.error.value}}</div>
    <form v-if="open&&canEdit" class="pointwise-form" @submit.prevent="submit">
      <p class="caption">{{spanHint}}。乱序可自动整理；重复波长读数冲突、覆盖不足或相邻跨度超限时拒绝，且绝不外推补齐。</p>
      <label>逐点测谱（每行“波长,读数”，也可粘贴两等长数据块）
        <textarea aria-label="逐点测谱" v-model="text" rows="6" placeholder="400,0.12&#10;412.5,0.15&#10;437.5,0.21" required></textarea>
      </label>
      <label>本次插值跨度上限（留空用库设置 {{library.max_interp_gap}}nm）
        <input aria-label="插值跨度上限" type="number" min="5" max="200" step="1" v-model.number="overrideGap"/>
      </label>
      <div class="pointwise-buttons">
        <button class="primary" :disabled="a.busy.value">对齐并保存原始谱</button>
        <button class="outline" type="button" @click="open=false">取消</button>
      </div>
    </form>
  </div>
</template>
