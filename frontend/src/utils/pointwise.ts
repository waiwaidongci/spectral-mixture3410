import {PointwiseImportInput} from '../types/domain';

export interface ParsedPoints{raw_wavelengths:number[];raw_values:number[];error:string}

/** 解析逐点测谱文本，支持两种粘贴形态：
 * 1. 两列：每行 "波长,读数"，分隔符可为逗号/空白/制表符/分号；
 * 2. 两整块：先粘全部波长再粘全部读数（空行分隔），长度需一致。
 * 乱序允许，交给后端排序；非数值/空数据在此先拦截并给出可读错误。
 */
export function parsePointwiseText(text:string):ParsedPoints{
  const clean=text.trim();
  if(!clean)return {raw_wavelengths:[],raw_values:[],error:'请粘贴逐点测谱（波长与读数）'};
  const lines=clean.split(/\r?\n/).map(l=>l.trim()).filter(Boolean);
  const rows=lines.map(l=>l.split(/[,，;；\s]+/).filter(Boolean));
  const twoCol=rows.every(r=>r.length===2);
  if(twoCol){
    const wl:number[]=[],val:number[]=[];
    for(const [a,b] of rows){
      const w=Number(a),v=Number(b);
      if(!Number.isFinite(w)||!Number.isFinite(v))return {raw_wavelengths:[],raw_values:[],error:`存在非数值行：${a} / ${b}`};
      wl.push(w);val.push(v);
    }
    return {raw_wavelengths:wl,raw_values:val,error:''};
  }
  // 整块形态：所有 token 前半为波长、后半为读数，或恰好两等长分组。
  const tokens=clean.split(/[,，;；\s]+/).filter(Boolean).map(Number);
  if(tokens.some(n=>!Number.isFinite(n)))return {raw_wavelengths:[],raw_values:[],error:'粘贴内容含非数值，请按两列或两等长块整理'};
  if(tokens.length%2!==0)return {raw_wavelengths:[],raw_values:[],error:'波长与读数数量不一致，无法逐点配对'};
  const half=tokens.length/2;
  return {raw_wavelengths:tokens.slice(0,half),raw_values:tokens.slice(half),error:''};
}

export function toPointwiseInput(text:string,maxGap:number|null|''):PointwiseImportInput{
  const parsed=parsePointwiseText(text);
  if(parsed.error)throw new Error(parsed.error);
  if(parsed.raw_wavelengths.length<2)throw new Error('逐点测谱至少需要两个测点');
  const gap=maxGap===''||maxGap==null||!Number.isFinite(maxGap)?null:maxGap;
  return {raw_wavelengths:parsed.raw_wavelengths,raw_values:parsed.raw_values,max_gap_nm:gap};
}
