// Probe illustration adapted from the existing MIT-licensed Cook Control theme.
import {escape,formatTemperature} from './inkbird-cook-session.mjs?v=1.2.0';

export function probeColor(channel){
  if(!channel.fresh||!channel.armed)return '#88988d';
  if(channel.status==='ready'||channel.status==='notified')return '#238458';
  return channel.target>0&&channel.temperature>=channel.target-5?'#b85a27':'#a77b21';
}

export function probeFigure(model,channel,color){
  const key=`probe-${model}-${channel}`,iht=model==='iht2pb',builtIn=iht&&channel==='1';
  if(builtIn)return `<svg class="probe-figure" viewBox="0 0 44 170" role="img" aria-label="IHT-2PB built-in tip"><rect x="8" y="6" width="28" height="76" rx="9" fill="#202327" stroke="#7a8288"/><rect x="13" y="22" width="18" height="24" rx="2" fill="#44bddd"/><circle cx="22" cy="62" r="4" fill="#44bddd"/><path d="M18 82h8v75l-4 10-4-10z" fill="#bcc3c8" stroke="#74808a"/><path d="M18 157h8l-4 10z" fill="${color}"/></svg>`;
  return `<svg class="probe-figure" viewBox="0 0 32 170" role="img" aria-label="${iht?'IHT-2PB external probe':'INT-14-BW wireless probe'}">
    <defs><linearGradient id="steel-${key}"><stop stop-color="#6c7075"/><stop offset=".28" stop-color="#eef1f3"/><stop offset=".5" stop-color="#c4c9ce"/><stop offset=".72" stop-color="#eef1f3"/><stop offset="1" stop-color="#5c6065"/></linearGradient><linearGradient id="handle-${key}"><stop stop-color="#0c0c0e"/><stop offset=".3" stop-color="#3a3a40"/><stop offset=".7" stop-color="#141418"/><stop offset="1" stop-color="#050506"/></linearGradient></defs>
    ${iht?`<path d="M16 22V8q0-6 9-6" fill="none" stroke="#777f86" stroke-width="3"/><rect x="10" y="22" width="12" height="24" rx="4" fill="#282c30"/>`:`<ellipse cx="16" cy="9" rx="8" ry="3" fill="url(#steel-${key})"/><path d="M8 9h16l-4 49h-8z" fill="url(#handle-${key})" stroke="#101114"/><text x="16" y="35" text-anchor="middle" fill="#d8dfe2" font-size="10" font-family="system-ui">${escape(channel)}</text>`}
    <rect x="12" y="${iht?46:58}" width="8" height="5" rx="1" fill="url(#steel-${key})"/><rect x="13" y="${iht?51:63}" width="6" height="91" fill="url(#steel-${key})"/><path d="M13 ${iht?142:154}h6l-3 12z" fill="${color}"/>
  </svg>`;
}

export function dial(channel,labels){
  const valid=Number.isFinite(channel.temperature),target=Number.isFinite(channel.target)&&channel.target>0;
  const progress=channel.fresh&&valid&&target?Math.max(0,Math.min(1,channel.target<=22?(channel.temperature>=channel.target?1:0):(channel.temperature-22)/(channel.target-22))):0;
  const circumference=2*Math.PI*52,arc=circumference*.75,color=probeColor(channel);
  return `<div class="dial" role="img" aria-label="${escape(formatTemperature(channel.temperature))}; ${escape(target?formatTemperature(channel.target):labels.noTarget)}"><svg viewBox="0 0 128 128" aria-hidden="true"><g transform="rotate(135 64 64)"><circle cx="64" cy="64" r="52" fill="none" stroke="var(--divider-color,#ddd)" stroke-width="9" stroke-linecap="round" stroke-dasharray="${arc} ${circumference}"/><circle cx="64" cy="64" r="52" fill="none" stroke="${color}" stroke-width="9" stroke-linecap="round" stroke-dasharray="${(arc*progress).toFixed(1)} ${circumference}"/></g></svg><div class="dial-label"><strong>${valid?channel.temperature.toFixed(1):'\u2014'}<small>\u00b0C</small></strong><span>${target?`${escape(labels.target)} ${channel.target}\u00b0`:escape(labels.noTarget)}</span></div></div>`;
}

export function sparkline(samples,channel,color,label){
  const rows=samples.map(s=>({x:s.at,y:s.channels[channel]?.temperature??null}));
  const valid=rows.filter(p=>Number.isFinite(p.y));
  if(!valid.length)return `<div class="spark-empty">${escape(label)}</div>`;
  const first=rows[0].x,last=Math.max(first+1,rows.at(-1).x),values=valid.map(p=>p.y);
  const low=values.reduce((a,b)=>Math.min(a,b),Infinity)-1,high=values.reduce((a,b)=>Math.max(a,b),-Infinity)+1;
  const x=v=>4+(v-first)/(last-first)*392,y=v=>52-(v-low)/(high-low)*44;
  let path='',previous=null;
  for(const point of rows){if(!Number.isFinite(point.y)){previous=null;continue;}path+=`${previous===null||point.x-previous>90?'M':'L'}${x(point.x).toFixed(1)},${y(point.y).toFixed(1)} `;previous=point.x;}
  return `<svg class="spark" viewBox="0 0 400 60" preserveAspectRatio="none" role="img" aria-label="${escape(label)}"><path d="M4 54H396" stroke="var(--divider-color,#ddd)"/><path d="${path}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>`;
}
