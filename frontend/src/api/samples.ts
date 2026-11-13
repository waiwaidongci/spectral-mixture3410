import {request} from './client';import {Sample,PointwiseImportInput,RealignResult} from '../types/domain';
export const getSamples=(id:number)=>request<Sample[]>(`/libraries/${id}/samples`);
export const annotateSample=(id:number,note:string)=>request(`/samples/${id}`,{method:'PATCH',body:JSON.stringify({note})});
export const importPointwiseSpectrum=(id:number,body:PointwiseImportInput)=>request<Sample>(`/samples/${id}/pointwise-spectrum`,{method:'POST',body:JSON.stringify(body)});
export const realignSample=(id:number)=>request<Sample>(`/samples/${id}/realign`,{method:'POST'});
export const realignLibrarySamples=(id:number)=>request<RealignResult>(`/libraries/${id}/realign-samples`,{method:'POST'});
