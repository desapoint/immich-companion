import { errorMessage } from '../data/mutationFeedback';
import { libraryData } from '../data/currentDataSource.svelte';
import type { RelationOption } from '../data/contracts';
import type { AlbumCreateDetails, TagCreateDetails } from '../components/V2RelationCreateModal.svelte';
import { LatestRequestController } from './latestRequest';

function mergeOptions(current:RelationOption[],incoming:RelationOption[],selected:string[],append:boolean){
  const selectedSet=new Set(selected);
  const retained=append?current:current.filter((option)=>selectedSet.has(option.value));
  return[...new Map([...retained,...incoming].map((option)=>[option.value,option])).values()];
}

export class AssetRelationOptionsController{
  albumOptions=$state<RelationOption[]>([]);
  tagOptions=$state<RelationOption[]>([]);
  albumCursor=$state<string|null>(null);
  tagCursor=$state<string|null>(null);
  albumQuery=$state('');
  tagQuery=$state('');
  albumLoading=$state(false);
  tagLoading=$state(false);
  error=$state('');
  private albumRequests=new LatestRequestController();
  private tagRequests=new LatestRequestController();
  private albumError='';
  private tagError='';
  private operationError='';

  private updateError(){this.error=this.operationError||this.albumError||this.tagError}

  async searchAlbums(queryText:string,selected:string[],append=false){
    if(this.albumLoading&&append)return;
    const request=this.albumRequests.begin();
    this.albumLoading=true;
    if(!append){this.albumQuery=queryText;this.albumCursor=null}
    try{
      const result=await libraryData.albums.searchOptions({query:append?this.albumQuery:queryText,pageSize:24,cursor:append?this.albumCursor:null,signal:request.signal});
      if(!this.albumRequests.isCurrent(request))return;
      this.albumOptions=mergeOptions(this.albumOptions,result.items,selected,append);
      this.albumCursor=result.nextCursor;
      this.albumError='';
      this.updateError();
    }catch(error){if(this.albumRequests.isCurrent(request)){this.albumError=errorMessage(error,'Album options could not be loaded.');this.updateError()}}finally{if(this.albumRequests.finish(request))this.albumLoading=false}
  }

  async searchTags(queryText:string,selected:string[],append=false){
    if(this.tagLoading&&append)return;
    const request=this.tagRequests.begin();
    this.tagLoading=true;
    if(!append){this.tagQuery=queryText;this.tagCursor=null}
    try{
      const result=await libraryData.tags.searchOptions({query:append?this.tagQuery:queryText,pageSize:24,cursor:append?this.tagCursor:null,signal:request.signal});
      if(!this.tagRequests.isCurrent(request))return;
      this.tagOptions=mergeOptions(this.tagOptions,result.items,selected,append);
      this.tagCursor=result.nextCursor;
      this.tagError='';
      this.updateError();
    }catch(error){if(this.tagRequests.isCurrent(request)){this.tagError=errorMessage(error,'Tag options could not be loaded.');this.updateError()}}finally{if(this.tagRequests.finish(request))this.tagLoading=false}
  }

  destroy(){this.albumRequests.cancel();this.tagRequests.cancel()}
  clearError(){this.albumError='';this.tagError='';this.operationError='';this.updateError()}

  async createAlbum(input:string|AlbumCreateDetails):Promise<RelationOption>{
    const details:AlbumCreateDetails=typeof input==='string'?{name:input,description:''}:input;
    try{
      const created=await libraryData.albums.create(details.name.trim(),details.description);
      if(!created)throw new Error('The album was not created.');
      const option:RelationOption={value:created.id,label:created.album_name,subtitle:`${created.asset_count.toLocaleString()} assets`};
      this.albumOptions=[option,...this.albumOptions.filter((item)=>item.value!==option.value)];
      this.operationError='';
      this.updateError();
      return option;
    }catch(error){
      const message=errorMessage(error,'The album could not be created.');
      this.operationError=message;
      this.updateError();
      throw new Error(message);
    }
  }

  async createTag(input:string|TagCreateDetails):Promise<RelationOption>{
    const details:TagCreateDetails=typeof input==='string'?{name:input,color:null,parentPath:''}:input;
    try{
      const created=await libraryData.tags.create(details.name.trim(),details.color,details.parentPath);
      if(!created)throw new Error('The tag was not created.');
      const option:RelationOption={value:created.id,label:created.tag_name,subtitle:`${created.asset_count.toLocaleString()} assets`};
      this.tagOptions=[option,...this.tagOptions.filter((item)=>item.value!==option.value)];
      this.operationError='';
      this.updateError();
      return option;
    }catch(error){
      const message=errorMessage(error,'The tag could not be created.');
      this.operationError=message;
      this.updateError();
      throw new Error(message);
    }
  }
}
