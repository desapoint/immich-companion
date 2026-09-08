import { mutationFeedback, errorMessage, pendingOperationFeedback, type OperationFeedback } from '../data/mutationFeedback';
import type { AssetSelectionTarget, MutationResult } from '../data/contracts';

export type AssetMutationRunner=(target:AssetSelectionTarget)=>Promise<MutationResult>;
export type AssetMutationPhase='idle'|'applying'|'refreshing';
export type AssetMutationRunOptions={
  refresh?:(result:MutationResult)=>Promise<void>;
  refreshError?:string;
};

export class AssetMutationController{
  feedback=$state<OperationFeedback|null>(null);
  error=$state('');
  busy=$state(false);
  phase=$state<AssetMutationPhase>('idle');
  action=$state('');
  retry=$state<(()=>Promise<void>)|null>(null);

  constructor(private refresh:()=>Promise<void>,private onSummary:(summary:string)=>void){}

  clearError(){this.error=''}
  clearOutcome(){this.feedback=null;this.error='';this.retry=null}

  async run(action:string,runner:AssetMutationRunner,target:AssetSelectionTarget,options:AssetMutationRunOptions={}){
    if(this.busy)return null;
    this.busy=true;
    this.phase='applying';
    this.action=action;
    this.error='';
    this.feedback=pendingOperationFeedback(action,'applying');
    this.retry=null;
    try{
      let result:MutationResult;
      try{
        result=await runner(target);
      }catch(error){
        this.feedback=null;
        this.error=errorMessage(error,`${action} could not be completed.`);
        return null;
      }

      const outcome=mutationFeedback(action,result);
      this.onSummary(outcome.detail);
      this.retry=result.failed.length?()=>this.run(action,runner,{kind:'ids',ids:result.failed.map((failure)=>failure.id)},options).then(()=>{}):null;

      this.phase='refreshing';
      this.feedback=pendingOperationFeedback(action,'refreshing');
      try{
        if(options.refresh)await options.refresh(result);else await this.refresh();
      }catch(error){
        this.error=errorMessage(error,options.refreshError??`${action} was applied, but the latest asset state could not be loaded.`);
      }
      this.feedback=outcome;
      return result;
    }finally{
      this.busy=false;
      this.phase='idle';
      this.action='';
    }
  }
}
