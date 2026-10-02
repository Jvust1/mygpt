/** Explicit manual text -> local packet. The IDs identify an unversioned input
 * container, NOT a real course/book/version. No request or storage is performed.
 */
const ordered=x=>Array.isArray(x)?x.map(ordered):x&&typeof x==='object'
  ?Object.fromEntries(Object.keys(x).sort().map(k=>[k,ordered(x[k])])):x;
export async function manualPacket(text,title=''){
  if(typeof text!=='string'||!text.trim()||text.length>8000||typeof title!=='string'||title.length>160)
    throw new TypeError('invalid manual selection');
  const source={course_id:'manual-input',book_id:'unversioned-local-input',book_version_id:'manual-unversioned',
    section_id:'selected',record_id:'paragraph-1',source_kind:'paragraph',layer:'source',layer_id:'original',portion:'body',
    title:title||'手动选段（未核验来源）',parts:[{kind:'text',text}],
    qualification:'用户手动提供；容器标识不代表教材、课程或版本已经核验。',parent_sources:[]};
  const bytes=new TextEncoder().encode(JSON.stringify(ordered(source)));
  const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');
  return {schema_version:'mygpt.selection-packet.v1',trust:'USER_SUPPLIED_UNVERIFIED',source,source_sha256:hash};
}
