import { mutationFeedback, errorMessage, type OperationFeedback } from '../data/mutationFeedback';
import type { AssetSelectionTarget, MutationResult } from '../data/contracts';

export type AssetMutationRunner=(target:AssetSelectionTarget)=>Promise<MutationResult>;

export class AssetMutationController{
  feedback=$state<OperationFeedback|null>(null);
  error=$state('');
  busy=$state(false);
  retry=$state<(()=>Promise<void>)|null>(null);

  constructor(private refresh:()=>Promise<void>,private onSummary:(summary:string)=>void){}

  clearError(){this.error=''}

  async run(action:string,runner:AssetMutationRunner,target:AssetSelectionTarget){
    if(this.busy)return null;
    this.busy=true;
    this.error='';
    try{
      const result=await runner(target);
      this.feedback=mutationFeedback(action,result);
      this.onSummary(this.feedback.detail);
      this.retry=result.failed.length?()=>this.run(action,runner,{kind:'ids',ids:result.failed.map((failure)=>failure.id)}).then(()=>{}):null;
      await this.refresh();
      return result;
    }catch(error){
      this.feedback=null;
      this.retry=null;
      this.error=errorMessage(error,`${action} could not be completed.`);
      return null;
    }finally{
      this.busy=false;
    }
  }
}
