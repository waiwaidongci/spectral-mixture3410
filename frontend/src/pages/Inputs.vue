<script setup lang="ts">
import {computed,ref,watch} from 'vue';
import {useRoute} from 'vue-router';
import {useResearchData} from '../hooks/useResearch';
import {useAuth} from '../stores/auth';
import {useAction} from '../hooks/useAction';
import {annotateSample} from '../api/samples';
import LibrarySelector from '../components/LibrarySelector.vue';
import SpectralPlot from '../components/SpectralPlot.vue';
import DataTable from '../components/common/DataTable.vue';
import Notice from '../components/common/Notice.vue';
import PointwiseImport from '../components/PointwiseImport.vue';
import AlignmentDetail from '../components/AlignmentDetail.vue';
import LibraryGapPanel from '../components/LibraryGapPanel.vue';
import {number,scientific} from '../utils/format';

const s=useResearchData(),auth=useAuth(),a=useAction(),route=useRoute();
const selected=ref(Number(route.query.library)||0);
const editing=ref(0),note=ref('');
const canEdit=computed(()=>auth.user?.role!=='viewer');
const library=computed(()=>s.libraries.find(l=>l.id===selected.value)||s.libraries[0]);
const pointwiseCount=computed(()=>s.samples.filter(x=>x.raw_wavelengths).length);

watch(()=>library.value?.id,id=>{if(id)s.loadLibrary(id)},{immediate:true});
async function save(){
  a.execute(async()=>{
    await annotateSample(editing.value,note.value);
    editing.value=0;
    await s.loadLibrary(library.value.id);
  });
}
async function reload(){await s.refresh();await s.loadLibrary(library.value.id);}
</script>

<template>
  <div class="page">
    <div class="page-title">
      <div>
        <p class="eyebrow">REFERENCE &amp; MIXTURE / 02</p>
        <h1>端元与样本<span>逐点测谱按所选库波长对齐，先于配比数值。</span></h1>
      </div>
    </div>

    <Notice :message="s.error||a.error.value" @retry="s.refresh"/>
    <LibrarySelector :libraries="s.libraries" :model-value="library?.id||0" @update:model-value="selected=$event"/>

    <div v-if="library" :class="['library-diagnostic',!library.supported?'warning':'']">
      <span>增广条件数 {{scientific(library.condition_number)}} · 插值跨度上限 {{number(library.max_interp_gap,0)}}nm</span>
      <p>{{library.reason}}</p>
    </div>

    <SpectralPlot v-if="library&&s.endmembers.length" :library="library" :endmembers="s.endmembers"/>

    <div class="section-heading"><h2>端元数值</h2><span>无量纲反射率 · 波段顺序固定</span></div>
    <DataTable :head="['端元',...(library?.wavelengths||[]).map(w=>w+'nm')]">
      <tr v-for="e in s.endmembers" :key="e.id">
        <td>{{e.name}}</td>
        <td v-for="(v,i) in e.spectrum" :key="i">{{number(v)}}</td>
      </tr>
    </DataTable>

    <LibraryGapPanel v-if="library" :library="library" :can-edit="canEdit" :pointwise-count="pointwiseCount" @changed="reload"/>

    <div class="section-heading"><h2>混合样本</h2><span>逐点导入留存原始谱与插值依据 · 禁止外推</span></div>
    <form v-if="editing" class="annotation" @submit.prevent="save">
      <label>样本备注<input aria-label="样本备注" v-model="note" minlength="8" required/></label>
      <button class="primary" :disabled="a.busy.value">保存备注</button>
      <button class="outline" type="button" @click="editing=0">取消</button>
    </form>

    <DataTable :head="['样本编号','名称','网格波段','测谱来源','观察备注','逐点对齐操作']">
      <template v-for="sample in s.samples" :key="sample.id">
        <tr>
          <td class="mono">{{sample.code}}</td>
          <td>{{sample.name}}</td>
          <td>{{sample.observed.length}}</td>
          <td>
            <span v-if="sample.raw_wavelengths" class="align-badge">逐点 {{sample.alignment?.raw_point_count}} 点 → {{sample.observed.length}} 网格</span>
            <span v-else class="legacy-badge">原始网格读数</span>
          </td>
          <td class="note-cell">{{sample.note}}</td>
          <td>
            <PointwiseImport :sample="sample" :library="library" :can-edit="canEdit" @saved="reload"/>
            <button v-if="canEdit" class="text-link" @click="editing=sample.id;note=sample.note">补充备注</button>
          </td>
        </tr>
        <tr v-if="sample.alignment" class="alignment-row">
          <td colspan="6"><AlignmentDetail :sample="sample"/></td>
        </tr>
      </template>
    </DataTable>
    <p class="caption">
      旧样本无逐点原始谱时，observed 即原始网格读数，可照常分析。规则更新后须从原始谱显式重算，新研究才采用新读数；
      既有研究的冻结快照与获批导出始终对应导入时的对齐结果。
    </p>
  </div>
</template>
