// Dashboard projection of cited research. Unknown quotes remain planning allowances.
export const categoriesFor = kind => ['venue','catering',kind==='wedding'?'photography':kind==='corporate'?'av':'entertainment'];
export const usd = n => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:2}).format(n/100);
const classify = text => /cater|cuisine|pizza|kitchen|food service/i.test(text)?'catering':/photograph/i.test(text)?'photography':/entertain|music|\bdj\b|band/i.test(text)?'entertainment':/audio|\bav\b|sound rental/i.test(text)?'av':/venue|event cent|event space|hall|hotel/i.test(text)?'venue':null;
export function candidates(report, location) {
  const rows=[];let context='';let category=null;let heading='';
  for(const part of report?.parts||[]) for(const seg of part) {
    if(!seg.url) {
      context+=seg.text;
      const headings=seg.text.split('\n').map(x=>x.trim()).filter(x=>/^\*\*.+\*\*$|^#{1,6}\s|^\d+[.)]\s/.test(x));
      for(const h of headings){heading=h.replace(/^#+\s*|\*\*/g,'').replace(/^\d+[.)]\s*/,'').trim();category=classify(heading)||category;}
      continue;
    }
    let url;try{url=new URL(seg.url);if(!['https:','http:'].includes(url.protocol))continue;}catch{continue;}
    const cat=classify(seg.text)||category||classify(context.slice(-1200))||'other';
    if(rows.some(r=>r.url===seg.url))continue;
    const label=heading&&!/services:|schedule|next steps|recommendations/i.test(heading)?heading:seg.text;
    rows.push({id:seg.url,url:seg.url,name:label.replace(/\*+/g,''),category:cat,location,summary:context.slice(-1400).replace(/\*\*/g,'').trim(),sourceTitle:seg.text});
    context='';
  }
  return rows;
}

export function buildLivePlan(event, saved={}) {
  const rows=candidates(event.agent?.research,event.location);
  const cats=[...new Set([...categoriesFor(event.kind),...rows.map(r=>r.category).filter(c=>c!=='other')])];
  // Allocate 70% of the budget to services, retaining room for allowances.
  // This is an editable budget allocation, NOT a prediction of supplier prices.
  const weights={venue:35,catering:25,photography:10,entertainment:10,av:10};
  const sum=cats.reduce((n,c)=>n+(weights[c]||10),0);
  const items=cats.map(category=>{
    const options=rows.filter(r=>r.category===category);
    const selected=options.find(r=>r.id===saved.selection?.[category])||options[0];
    const custom=saved.costs?.[category];
    const cost=Number.isSafeInteger(custom)&&custom>=0&&custom<=10000000000?custom:Math.floor(event.budget_cents*.7*(weights[category]||10)/sum);
    return {...selected,id:category,category,name:selected?.name||`${category[0].toUpperCase()+category.slice(1)} — supplier still needed`,options,cost_cents:cost,cost_basis:custom!==undefined?'Your provisional estimate':'Budget allocation — quote needed',missing:!selected};
  });
  const subtotal=items.reduce((n,r)=>n+r.cost_cents,0),fees=Math.ceil(subtotal*.15),reserve=Math.ceil(event.budget_cents*.1);
  return {items,candidates:rows,subtotal,fees,reserve,total:subtotal+fees+reserve,provisional:true};
}

export function researchTimeline(event) {
  const text=(event.agent?.research?.parts||[]).map(p=>p.map(s=>s.url?'':s.text).join('')).join('\n');
  const section=text.split(/(?:suggested\s+)?schedule\s*:?\*{0,2}/i)[1]?.split(/next steps/i)[0]||'';
  const rows=[];
  for(const line of section.split('\n')){
    const m=line.match(/(\d{1,2}):(\d{2})\s*(AM|PM)\s*[–—-]\s*(\d{1,2}):(\d{2})\s*(AM|PM)\s*:?\*{0,2}\s*(.+)/i);
    if(!m)continue;
    const hour=Number(m[1])%12+(m[3].toUpperCase()==='PM'?12:0);
    const at=`${event.date}T${String(hour).padStart(2,'0')}:${m[2]}`;
    rows.push({at,task:m[7].replace(/\*+/g,'').trim(),basis:'Suggested in research; confirm timing'});
  }
  if(rows.length)return rows;
  const start=new Date(`${event.date}T${event.start_time}:00`);
  return [[0,'Guest arrival and welcome'],[30,'Opening activity'],[60,'Food and refreshments'],[Math.max(90,event.duration_hours*60-60),'Main celebration'],[event.duration_hours*60,'Guest departure']].map(([minute,task])=>{
    const d=new Date(start.getTime()+minute*60000);
    const at=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}T${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
    return {at,task,basis:'Suggested template — editable in your next instruction'};
  });
}
