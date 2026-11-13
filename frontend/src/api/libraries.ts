import {request} from './client';import {Library} from '../types/domain';
export interface GapUpdateResult{library_id:number;max_interp_gap:number;pointwise_samples_pending_realignment:number}
export const getLibraries=()=>request<Library[]>('/libraries');
export const updateInterpolationGap=(id:number,max_interp_gap:number)=>request<GapUpdateResult>(`/libraries/${id}/interpolation-gap`,{method:'PATCH',body:JSON.stringify({max_interp_gap})});
