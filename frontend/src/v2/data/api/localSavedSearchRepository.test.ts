import { describe,expect,it } from 'vitest';
import { createLocalSavedSearchRepository } from './localSavedSearchRepository';

describe('local V2 saved searches',()=>{
  it('persists create, update, search, and delete operations without demo seeds',async()=>{
    const values=new Map<string,string>(),storage={getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value)}};
    const repository=createLocalSavedSearchRepository(storage),criteria={mode:'simple' as const,filters:{filename:'sunset'},sort:{field:'takenDate' as const,direction:'desc' as const}};
    expect((await repository.search({pageSize:24})).items).toEqual([]);
    const created=await repository.create({name:' Sunset review ',description:' Later ',criteria});
    expect(created).toMatchObject({name:'Sunset review',description:'Later'});
    await expect(repository.update(created.id,{name:'Sunsets'})).resolves.toEqual({affectedIds:[created.id],failed:[]});
    expect((await createLocalSavedSearchRepository(storage).search({pageSize:24,query:'sunsets'})).items).toHaveLength(1);
    await expect(repository.delete([created.id])).resolves.toEqual({affectedIds:[created.id],failed:[]});
  });
});
