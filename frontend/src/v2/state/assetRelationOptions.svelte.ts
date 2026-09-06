import { errorMessage } from '../data/mutationFeedback';
import { libraryData } from '../data/currentDataSource.svelte';
import type { RelationOption } from '../data/contracts';

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
  private albumRequest=0;
  private tagRequest=0;

  async searchAlbums(queryText:string,selected:string[],append=false){
    const request=++this.albumRequest;
    this.albumLoading=true;
    if(!append){this.albumQuery=queryText;this.albumCursor=null}
    try{
      const result=await libraryData.albums.searchOptions({query:append?this.albumQuery:queryText,pageSize:24,cursor:append?this.albumCursor:null});
      if(request!==this.albumRequest)return;
      this.albumOptions=mergeOptions(this.albumOptions,result.items,selected,append);
      this.albumCursor=result.nextCursor;
      this.error='';
    }catch(error){this.error=errorMessage(error,'Album options could not be loaded.')}finally{if(request===this.albumRequest)this.albumLoading=false}
  }

  async searchTags(queryText:string,selected:string[],append=false){
    const request=++this.tagRequest;
    this.tagLoading=true;
    if(!append){this.tagQuery=queryText;this.tagCursor=null}
    try{
      const result=await libraryData.tags.searchOptions({query:append?this.tagQuery:queryText,pageSize:24,cursor:append?this.tagCursor:null});
      if(request!==this.tagRequest)return;
      this.tagOptions=mergeOptions(this.tagOptions,result.items,selected,append);
      this.tagCursor=result.nextCursor;
      this.error='';
    }catch(error){this.error=errorMessage(error,'Tag options could not be loaded.')}finally{if(request===this.tagRequest)this.tagLoading=false}
  }
}
