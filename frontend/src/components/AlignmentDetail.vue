<script setup lang="ts">
import {ref} from 'vue';
import {Sample} from '../types/domain';
import {number,time} from '../utils/format';
const props=defineProps<{sample:Sample}>();
const show=ref(false);
</script>
<template>
  <div v-if="sample.alignment" class="alignment-detail">
    <button class="text-link" @click="show=!show">{{show?'收起插值依据':'查看插值依据'}}</button>
    <div v-if="show" class="alignment-body">
      <p class="caption">
        规则 {{sample.alignment.rule_version}} · {{sample.alignment.method}} · 原始测点 {{sample.alignment.raw_point_count}} 个 →
        库网格 {{sample.alignment.grid_point_count}} 点 · 跨度上限 {{number(sample.alignment.max_gap_nm,0)}}nm ·
        外推：{{sample.alignment.extrapolation==='forbidden'?'禁止':'—'}} · 对齐时间 {{sample.aligned_at?time(sample.aligned_at):'—'}}
      </p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>库波长(nm)</th><th>左测点(nm)</th><th>右测点(nm)</th><th>左读数</th><th>右读数</th><th>右权重</th><th>跨度(nm)</th><th>取值</th><th>命中</th></tr></thead>
          <tbody>
            <tr v-for="(b,i) in sample.alignment.interpolation_basis" :key="i">
              <td class="mono">{{number(b.target_wavelength,2)}}</td>
              <td class="mono">{{number(b.left_wavelength,2)}}</td>
              <td class="mono">{{number(b.right_wavelength,2)}}</td>
              <td>{{number(b.left_value)}}</td>
              <td>{{number(b.right_value)}}</td>
              <td>{{number(b.weight_right)}}</td>
              <td class="mono">{{number(b.span,2)}}</td>
              <td>{{number(b.aligned_value)}}</td>
              <td>{{b.exact?'精确测点':'内插'}}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
