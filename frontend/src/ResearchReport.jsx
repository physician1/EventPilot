import React from 'react';

// Render a small Markdown subset as React nodes, never raw model HTML.
function safeUrl(value) {
  try { return ['https:', 'http:'].includes(new URL(value).protocol); }
  catch { return false; }
}

function inline(text, sources, key='') {
  const pattern = /(\uE000\d+\uE001|\*\*[^*]+\*\*|\*[^*\n]+\*|\[[^\]]+\]\(https?:\/\/[^\s)]+\))/g;
  return text.split(pattern).filter(Boolean).map((chunk,i) => {
    const id=`${key}-${i}`;
    if (chunk.startsWith('\uE000')) {
      const source=sources[Number(chunk.slice(1,-1))];
      return source && safeUrl(source.url) ? <a className="source-link" key={id} href={source.url} target="_blank" rel="noopener noreferrer">{source.text || 'Source'} ↗</a> : null;
    }
    if (chunk.startsWith('**')) return <strong key={id}>{chunk.slice(2,-2)}</strong>;
    if (chunk.startsWith('*')) return <em key={id}>{chunk.slice(1,-1)}</em>;
    const link=chunk.match(/^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/);
    if (link && safeUrl(link[2])) return <a key={id} href={link[2]} target="_blank" rel="noopener noreferrer">{link[1]}</a>;
    return <React.Fragment key={id}>{chunk}</React.Fragment>;
  });
}

export default function ResearchReport({report}) {
  const sources=[];
  const text=(report?.parts || []).map(part=>part.map(segment=>{
    if (!segment.url) return segment.text.replace(/[\uE000\uE001]/g,'');
    const index=sources.push(segment)-1;
    return ` \uE000${index}\uE001 `;
  }).join('')).join('\n\n');
  const lines=text.replace(/\r\n/g,'\n').split('\n');
  const blocks=[];
  for(let i=0;i<lines.length;) {
    const line=lines[i].trim();
    if(!line) {i++;continue;}
    const heading=line.match(/^(?:#{1,6}\s+(.+)|\*\*(.+)\*\*)$/);
    if(heading) {blocks.push(<h3 key={i}>{inline(heading[1]||heading[2],sources,i)}</h3>);i++;continue;}
    const list=line.match(/^(?:([-*])|\d+[.)])\s+(.+)/);
    if(list) {
      const ordered=!list[1]; const items=[];const start=i;
      while(i<lines.length) {
        const item=lines[i].trim().match(ordered?/^\d+[.)]\s+(.+)/:/^[-*]\s+(.+)/);
        if(!item) break;
        items.push(<li key={i}>{inline(item[1],sources,i)}</li>);i++;
      }
      blocks.push(ordered?<ol key={start}>{items}</ol>:<ul key={start}>{items}</ul>);continue;
    }
    blocks.push(<p key={i}>{inline(line,sources,i)}</p>);i++;
  }
  return <div className="research-report">{blocks}</div>;
}
