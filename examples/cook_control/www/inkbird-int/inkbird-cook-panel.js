import {escape as e, selectedDevice, formatTemperature as temp, csv, loadHistory, series} from './inkbird-cook-session.mjs?v=1.2.0';
import {probeColor,probeFigure,dial,sparkline} from './inkbird-cook-visuals.mjs?v=1.2.0';

const style = `
:host{display:block;color:var(--primary-text-color);font:14px system-ui;letter-spacing:0;max-width:1400px;margin:0 auto;padding:12px 20px 28px}
*{box-sizing:border-box}button,input,select{font:inherit;letter-spacing:0;color:inherit}
button{cursor:pointer;background:var(--secondary-background-color,#eee);border:1px solid var(--divider-color,#ccc);border-radius:6px;min-height:42px;padding:8px 12px}
button:hover{border-color:var(--primary-color)}button:disabled{opacity:.5;cursor:default}button.primary{background:var(--primary-color);color:var(--text-primary-color,#fff)}
ha-icon{--mdc-icon-size:20px;vertical-align:middle}.icon{width:42px;padding:8px;flex:none}
input,select{background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#ccc);border-radius:5px;padding:10px;min-width:0;max-width:100%;min-height:42px}
input[type=checkbox]{accent-color:var(--primary-color);width:22px;min-height:22px;height:22px}input[type=number]{width:100px}
label{display:flex;gap:8px;align-items:center;flex-wrap:wrap}label.field{align-items:flex-start;flex-direction:column;gap:5px}.field input{width:100%}
h1{font-size:24px;margin:0}h2{font-size:18px;margin:0}h3{font-size:16px;margin:0}p{margin:8px 0;line-height:1.5}.muted,small{color:var(--secondary-text-color);line-height:1.5}
header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:14px 0 18px;border-bottom:1px solid var(--divider-color)}
.toolbar,.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.toolbar select{max-width:100%;flex:1;min-width:190px}.toolbar{margin:18px 0}
.overview{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}.overview button{font-size:13px;text-align:left}.overview .chosen{border:2px solid var(--primary-color)}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:18px 0}
article{background:var(--ha-card-background,var(--card-background-color,#fff));border:1px solid var(--divider-color);border-radius:8px;padding:18px;min-width:0;overflow-wrap:anywhere}
.status{font-size:13px;font-weight:600;color:var(--probe-color)}
.probe-card{border-top:3px solid var(--probe-color)}.probe-tag{color:var(--probe-color);font-weight:700;margin-right:8px}
.instrument{display:grid;grid-template-columns:30px 144px minmax(0,1fr);gap:14px;align-items:center;min-height:170px;margin:8px 0}.probe-figure{width:30px;height:166px;display:block;margin:auto}
.dial{position:relative;width:136px;height:136px;margin:auto}.dial svg{width:100%;height:100%;display:block}.dial-label{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px}.dial-label strong{font:650 27px ui-monospace,monospace;white-space:nowrap}.dial-label small{font:13px system-ui}.dial-label span{font-size:12px;color:var(--secondary-text-color)}
.metrics{display:grid;gap:7px;font-size:14px;min-width:0}.metrics div{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap}.metrics b{font-weight:600}.metrics small{font-size:12px}
.spark{display:block;width:100%;height:64px;margin:8px 0}.spark-empty{height:64px;display:flex;align-items:center;font-size:12px;color:var(--secondary-text-color);border-bottom:1px solid var(--divider-color)}
.probe-settings{border-top:1px solid var(--divider-color);padding-top:10px;margin-top:12px}.probe-settings summary{cursor:pointer;min-height:32px;color:var(--secondary-text-color)}.probe-settings .settings{padding-top:12px}.custom-preset{border-left:3px solid var(--primary-color);padding:12px;display:grid;gap:12px;background:var(--secondary-background-color)}
.settings{display:grid;gap:14px}.error{border-left:4px solid var(--error-color,#c33);padding:12px;margin:12px 0;overflow-wrap:anywhere}
.session{display:flex;justify-content:space-between;gap:12px;align-items:end;flex-wrap:wrap;padding:16px 0;border-bottom:1px solid var(--divider-color)}.session .field{flex:1;min-width:180px}
.history{width:100%;border-collapse:collapse;margin:16px 0}.history td,.history th{padding:12px 8px;border-bottom:1px solid var(--divider-color);text-align:left;overflow-wrap:anywhere}.history button{text-align:left}
canvas{display:block;width:100%;height:260px}.legend{display:flex;gap:12px;flex-wrap:wrap;margin:8px 0}.legend span{border-bottom:3px solid var(--line);padding:3px}
.split{display:flex;justify-content:space-between;gap:8px;align-items:center}.split>*{min-width:0}.event{padding:8px 0;border-bottom:1px solid var(--divider-color)}
@media(max-width:760px){.grid{grid-template-columns:minmax(0,1fr)}}
@media(max-width:550px){h1{font-size:22px}.history th:nth-child(3),.history td:nth-child(3){display:none}.session button{flex:1}.grid{gap:10px}article{padding:14px}.instrument{grid-template-columns:26px 128px minmax(0,1fr);gap:9px}.dial{width:124px;height:124px}.metrics{font-size:13px;gap:6px}}
@media(max-width:360px){:host{padding-left:10px;padding-right:10px}.instrument{grid-template-columns:24px 120px minmax(0,1fr);gap:6px}.dial{width:116px;height:116px}.metrics div{display:block}.metrics b{display:block}}
`;

class CookPanel extends HTMLElement {
  constructor(){super();this.attachShadow({mode:'open'});this.data={devices:[],history:[]};this.view='';this.error='';this.busy=false;this.alive=false;}
  setConfig(config){this.config=config;this.render();}
  set hass(value){this._hass=value;const language=value.states['input_select.bbq_language']?.state,backend=value.states['sensor.inkbird_cook_control']?.state;if(language!==this.language||backend!==this.backendStatus){this.language=language;this.backendStatus=backend;this.render();}if(this.isConnected)this.connect();}
  getCardSize(){return 8;}
  connectedCallback(){this.alive=true;this.connect();}
  disconnectedCallback(){this.alive=false;this.unsubscribe?.();this.unsubscribe=null;this.connection=null;this.resize?.disconnect();}
  t(en,it){return this.language==='Italiano'?it:en;}
  async connect(){
    if(!this._hass||this.connection===this._hass.connection)return;
    this.unsubscribe?.();this.connection=this._hass.connection;
    try{
      const unsubscribe=await this.connection.subscribeMessage(data=>{this.data=data;this.render();},{type:'inkbird_cook_control/subscribe'});
      if(!this.alive){unsubscribe();return;}this.unsubscribe=unsubscribe;
      this.error='';this.render();
    }catch(err){this.connection=null;this.error=this.t('Cook Control backend is unavailable. Check installation and administrator access.','Backend Cook Control non disponibile. Controlla installazione e accesso amministratore.');this.render();}
  }
  call(action,payload={}){return this._hass.callWS({type:'inkbird_cook_control/command',action,payload});}
  async act(action,payload){
    this.busy=true;this.error='';
    try{this.data=await this.call(action,payload);}
    catch(err){this.error=err.message||String(err);}
    finally{this.busy=false;this.render();}
  }
  selected(){
    let stored='';try{stored=localStorage.getItem(`inkbird-cook-view:${this._hass?.user?.id||'local'}`)||'';}catch{}
    return selectedDevice(this.data.devices,this.view||stored||this.data.initial_device);
  }
  select(id){this.view=id;try{localStorage.setItem(`inkbird-cook-view:${this._hass?.user?.id||'local'}`,id);}catch{}this.render(true);}
  channelName(device,layout,config){
    if(config.name!==layout.name)return config.name;
    return device.model==='int14_bw'?`${this.t('Probe','Sonda')} ${layout.id}`:[this.t('Built-in tip','Punta integrata'),this.t('External 1','Esterna 1'),this.t('External 2','Esterna 2')][Number(layout.id)-1];
  }
  render(force=false){
    if(!this.config||(!force&&this.shadowRoot.activeElement?.matches('input:not([type=checkbox]),select')))return;
    const d=this.selected();
    this.openCards=new Set([...this.shadowRoot.querySelectorAll('details[open]')].map(el=>el.closest('[data-channel]')?.dataset.channel));
    this.shadowRoot.innerHTML=`<style>${style}</style><header><h1>Cook Control</h1><ha-icon icon="mdi:grill"></ha-icon></header>
      ${this.error?`<div class="error" role="alert">${e(this.error)}</div>`:''}
      ${this.backendStatus!=='active'?`<div class="error" role="alert">${this.t('Cook Control backend is not active. Alerts are not being processed.','Il backend Cook Control non e attivo. Gli avvisi non vengono elaborati.')}</div>`:''}
      ${this.config.history?this.renderHistory():d?this.renderCook(d):`<p>${this.t('Waiting for registered INT-14-BW and IHT-2PB thermometers.','In attesa dei termometri INT-14-BW e IHT-2PB registrati.')}</p>`}`;
    this.bind(d);
    if(this.config.history&&this.history)this.draw(this.history);
    else if(d?.recent?.length)this.draw({summary:{layout:d.layout},samples:d.recent});
  }
  renderCook(d){
    const armed=device=>Object.values(device.channels).filter(c=>c.armed).length;
    return `<div class="overview">${this.data.devices.map(device=>`<button class="${device.id===d.id?'chosen':''}" data-view="${e(device.id)}">${e(device.alias)}<br><small>${armed(device)} ${armed(device)===1?this.t('alert on','avviso attivo'):this.t('alerts on','avvisi attivi')}</small></button>`).join('')}</div>
      <div class="toolbar"><select aria-label="${this.t('Thermometer','Termometro')}" id="device">${this.data.devices.map(device=>`<option value="${e(device.id)}" ${device.id===d.id?'selected':''}>${e(device.alias)}</option>`).join('')}</select><button class="icon" id="rename" title="${this.t('Rename thermometer','Rinomina termometro')}"><ha-icon icon="mdi:pencil-outline"></ha-icon></button></div>
      <div class="muted">${e(d.name)} &middot; ${d.model==='int14_bw'?'INT-14-BW &middot; 4 '+this.t('probes, food + ambient','sonde, cuore + ambiente'):'IHT-2PB &middot; '+this.t('built-in tip and 2 external probes','punta integrata e 2 sonde esterne')}</div>
      <div class="session">${d.cook?`<div><h2>${e(d.cook.name)}</h2><small>${new Date(d.cook.started*1000).toLocaleString()}</small></div><button id="finish"><ha-icon icon="mdi:stop-circle-outline"></ha-icon> ${this.t('Finish cook','Termina cottura')}</button>`:`<label class="field">${this.t('Cook name','Nome cottura')}<input id="cookname" maxlength="100" placeholder="${this.t('Sunday BBQ','Grigliata della domenica')}"></label><button id="start" class="primary"><ha-icon icon="mdi:play-outline"></ha-icon> ${this.t('Start recording','Avvia storico')}</button>`}</div>
      <div class="grid">${d.layout.map(layout=>this.renderChannel(d,layout)).join('')}</div>
      ${d.recent?.length?`<h2>${this.t('Recent temperatures','Temperature recenti')}</h2><canvas role="img" aria-label="${this.t('Recent temperature trend','Andamento recente delle temperature')}"></canvas>`:''}`;
  }
  renderChannel(d,layout){
    const c=d.channels[layout.id],name=this.channelName(d,layout,c);
    const statuses={off:this.t('Alert off','Avviso spento'),stale:this.t('Waiting for fresh readings','In attesa di letture recenti'),cooking:this.t('Alert on','Avviso attivo'),ready:this.t('Above target','Sopra soglia'),notified:this.t('Notification sent','Avviso inviato')};
    const iht=d.model==='iht2pb',color=probeColor(c),editing=this.customEditor?.device===d.id&&this.customEditor?.channel===layout.id;
    const status=c.status==='cooking'&&c.fresh&&c.target>0&&c.temperature>=c.target-5?this.t('Near target','Vicino alla soglia'):statuses[c.status]||e(c.status);
    return `<article data-channel="${layout.id}" class="probe-card ${c.fresh?'':'stale'}" style="--probe-color:${color}"><div class="split"><h3><span class="probe-tag">${iht?e(layout.name):'P'+layout.id}</span>${e(name===layout.name?'':name)}</h3><ha-icon icon="mdi:thermometer-probe"></ha-icon></div>
      <p class="status">${status}${c.status==='ready'?` &middot; ${Math.min(30,Math.floor(c.ready_seconds))}/30 s`:''}</p>
      <div class="instrument">${probeFigure(d.model,layout.id,color)}${dial(c,{target:this.t('target','soglia'),noTarget:this.t('No target','Nessuna soglia')})}<div class="metrics">
      ${!iht?`<div><span>${this.t('Ambient','Ambiente')}</span><b>${temp(c.ambient)}</b></div>`:''}
      <div><span>${this.t('HA target','Soglia HA')}</span><b>${c.target>0?temp(c.target):'\u2014'}</b></div>
      <div><span>${this.t(iht?'Device alarm':'Station alarm',iht?'Allarme IHT':'Allarme station')}</span><b>${temp(c.device_target)}</b></div>
      <div><span>${this.t('Battery','Batteria')}</span><b>${Number.isFinite(c.battery)?`${c.battery}%`:iht&&Number.isFinite(c.battery_raw)?`${this.t('level','livello')} ${c.battery_raw}`:'\u2014'}</b></div>
      ${c.battery_suspect?`<small>${this.t('Suspect battery report','Dato batteria sospetto')}</small>`:''}
      <small>${c.fresh?this.t('Recent reading','Lettura recente'):this.t('No recent reading','Nessuna lettura recente')}</small></div></div>
      ${sparkline(d.recent||[],layout.id,color,this.t('Temperature trend','Andamento temperatura'))}
      <div class="split"><label>${this.t('HA target','Soglia HA')} <input data-setting="target" type="number" min="0" max="350" step="1" value="${c.target}" aria-label="${this.t('Target in Celsius','Soglia in gradi Celsius')}"> \u00b0C</label><label><input data-setting="armed" type="checkbox" ${c.armed?'checked':''} ${this.busy?'disabled':''}>${this.t('Alert','Avviso')}</label></div>
      <details class="probe-settings" ${this.openCards?.has(layout.id)||editing?'open':''}><summary>${this.t('Name and presets','Nome e preset')}</summary><div class="settings"><label class="field">${this.t('Food / probe name','Pietanza / nome sonda')}<input data-setting="name" value="${e(c.name===layout.name?name:c.name)}" maxlength="100"></label>
      <select data-preset aria-label="Preset"><option value="">${this.t('Preset','Preset')}</option>${[['Beef Brisket',93],['Chicken',74],['Medium Steak',57],['Pork Ribs',90],['Salmon',52]].map(([label,value])=>`<option value="${label}|${value}">${label} &middot; ${value}\u00b0C</option>`).join('')}<option value="custom">${this.t('My preset','Il mio preset')}</option></select>
      ${editing?this.renderCustomPreset():''}</div></details>
      ${c.status==='notified'?`<div class="row"><button data-reminder="snooze" title="${this.t('Repeat after the snooze interval','Ripeti dopo l\'intervallo di rinvio')}"><ha-icon icon="mdi:alarm-snooze"></ha-icon> Snooze</button><button data-reminder="rest"><ha-icon icon="mdi:timer-outline"></ha-icon> ${this.t('Rest','Riposo')}</button><button class="icon" data-reminder="dismiss" title="${this.t('Cancel reminders','Annulla promemoria')}"><ha-icon icon="mdi:bell-off-outline"></ha-icon></button></div>`:''}
      ${c.snooze||c.rest?`<small>${this.t('Reminder','Promemoria')}: ${new Date((c.snooze||c.rest)*1000).toLocaleTimeString()}</small>`:''}</article>`;
  }
  renderCustomPreset(){const draft=this.customEditor.draft;return `<div class="custom-preset"><h3>${this.t('My preset','Il mio preset')}</h3><label class="field">${this.t('Preset name','Nome preset')}<input data-custom="name" value="${e(draft.name)}" maxlength="100"></label><label>${this.t('Temperature','Temperatura')} <input data-custom="target" type="number" min="1" max="350" step="1" value="${draft.target}"> \u00b0C</label><div class="row"><button data-custom-action="save" title="${this.t('Save preset without changing the cook','Salva il preset senza cambiare la cottura')}"><ha-icon icon="mdi:content-save-outline"></ha-icon> ${this.t('Save','Salva')}</button><button data-custom-action="apply" class="primary">${this.t('Use on this probe','Usa su questa sonda')}</button><button class="icon" data-custom-action="cancel" title="${this.t('Close without applying','Chiudi senza applicare')}"><ha-icon icon="mdi:close"></ha-icon></button></div>${this.presetSaved?`<small>${this.t('Preset saved','Preset salvato')}</small>`:''}</div>`;}
  renderHistory(){
    return `<h2 style="margin-top:20px">${this.t('Cooking history','Storico cotture')}</h2><table class="history"><thead><tr><th>${this.t('Cook','Cottura')}</th><th>${this.t('Thermometer','Termometro')}</th><th>${this.t('Started','Inizio')}</th></tr></thead><tbody>${this.data.history.map(row=>`<tr><td><button data-history="${row.id}">${e(row.name)}${row.ended?'':` &middot; ${this.t('active','in corso')}`}</button></td><td>${e(row.device_name)}</td><td>${new Date(row.started*1000).toLocaleString()}</td></tr>`).join('')}</tbody></table>
      ${this.history?`<div class="split"><h2>${e(this.history.summary.name)}</h2><div class="row"><button data-export="csv"><ha-icon icon="mdi:download"></ha-icon> CSV</button><button data-export="json" title="${this.t('Download full session','Scarica sessione completa')}">JSON</button></div></div><div class="legend">${this.history.summary.layout.map((c,i)=>`<span style="--line:${['#168b89','#e38b19','#ca4a72','#6476d2'][i]}">${e(c.name)}</span>`).join('')}</div><canvas aria-label="${this.t('Recorded temperatures in Celsius','Temperature registrate in gradi Celsius')}" role="img"></canvas><small>${this.t('Solid: food. Dotted: ambient. Gaps: no recent reading.','Linea continua: cuore. Tratteggio: ambiente. Vuoti: nessuna lettura recente.')}</small>
      <h3 style="margin-top:18px">${this.t('Session events','Eventi della cottura')}</h3>${this.history.events.slice(-80).reverse().map(event=>`<div class="event"><small>${new Date(event.at*1000).toLocaleString()}</small> &middot; ${e(event.kind)}${event.channel?' &middot; '+this.t('Probe','Sonda')+' '+e(event.channel):''}${event.result?' &middot; '+e(event.result):''}</div>`).join('')}`:`<p class="muted">${this.t('Recordings start when you start a cook or enable its first alert.','La registrazione parte quando avvii una cottura o attivi il primo avviso.')}</p>`}`;
  }
  bind(d){
    this.shadowRoot.querySelectorAll('[data-view]').forEach(el=>el.onclick=()=>this.select(el.dataset.view));
    const select=this.shadowRoot.querySelector('#device');if(select)select.onchange=()=>this.select(select.value);
    const rename=this.shadowRoot.querySelector('#rename');if(rename)rename.onclick=()=>{const name=prompt(this.t('Thermometer name','Nome termometro'),d.alias);if(name?.trim())this.act('rename',{device_id:d.id,name});};
    const start=this.shadowRoot.querySelector('#start');if(start)start.onclick=()=>this.act('start',{device_id:d.id,name:this.shadowRoot.querySelector('#cookname').value});
    const finish=this.shadowRoot.querySelector('#finish');if(finish)finish.onclick=()=>{if(confirm(this.t('Finish this cook and switch off only its alerts?','Terminare questa cottura e spegnere solo i suoi avvisi?')))this.act('finish',{device_id:d.id});};
    this.shadowRoot.querySelectorAll('[data-setting]').forEach(el=>el.onchange=()=>{const field=el.dataset.setting;this.act('configure',{device_id:d.id,channel:el.closest('[data-channel]').dataset.channel,settings:{[field]:field==='armed'?el.checked:field==='target'?Number(el.value):el.value}});});
    this.shadowRoot.querySelectorAll('[data-preset]').forEach(el=>el.onchange=()=>{if(!el.value)return;const channel=el.closest('[data-channel]').dataset.channel;if(el.value==='custom'){const stored=this._hass.states['input_text.bbq_custom_name']?.state;this.customEditor={device:d.id,channel,draft:{name:stored&&!['unknown','unavailable'].includes(stored)?stored:this.t('Custom','Personalizzato'),target:Number(this._hass.states['input_number.bbq_custom_target']?.state)||60}};this.presetSaved=false;this.render(true);return;}const [name,target]=el.value.split('|');this.act('configure',{device_id:d.id,channel,settings:{name,target:Number(target)}});});
    this.shadowRoot.querySelectorAll('[data-custom]').forEach(el=>el.oninput=()=>{this.customEditor.draft[el.dataset.custom]=el.dataset.custom==='target'?Number(el.value):el.value;this.presetSaved=false;});
    this.shadowRoot.querySelectorAll('[data-custom-action]').forEach(el=>el.onclick=()=>this.customPreset(el.dataset.customAction));
    this.shadowRoot.querySelectorAll('[data-reminder]').forEach(el=>el.onclick=()=>this.act(el.dataset.reminder,{device_id:d.id,channel:el.closest('[data-channel]').dataset.channel}));
    this.shadowRoot.querySelectorAll('[data-history]').forEach(el=>el.onclick=async()=>{try{this.history=await loadHistory((...args)=>this.call(...args),el.dataset.history);this.error='';}catch(err){this.error=err.message;}this.render(true);});
    this.shadowRoot.querySelectorAll('[data-export]').forEach(el=>el.onclick=()=>{const format=el.dataset.export;const blob=new Blob([format==='csv'?csv(this.history):JSON.stringify(this.history,null,2)],{type:format==='csv'?'text/csv;charset=utf-8':'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`cook-${this.history.summary.id}.${format}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  }
  async customPreset(action){
    if(action==='cancel'){this.customEditor=null;this.render(true);return;}
    const editor=this.customEditor,draft=editor.draft,helper=this._hass.states['input_number.bbq_custom_target'];
    if(!draft.name.trim()||draft.name.length>100||!Number.isFinite(draft.target)||draft.target<=0||draft.target>Math.min(350,helper?.attributes?.max??350)||draft.target<(helper?.attributes?.min??0)){this.error=this.t('Enter a preset name and a valid temperature.','Inserisci un nome e una temperatura valida.');this.render(true);return;}
    if(action==='apply'){await this.act('configure',{device_id:editor.device,channel:editor.channel,settings:{name:draft.name.trim(),target:draft.target}});if(!this.error)this.customEditor=null;this.render(true);return;}
    this.busy=true;try{await this._hass.callService('input_number','set_value',{entity_id:'input_number.bbq_custom_target',value:draft.target});await this._hass.callService('input_text','set_value',{entity_id:'input_text.bbq_custom_name',value:draft.name.trim()});this.presetSaved=true;this.error='';}catch(err){this.error=err.message||String(err);}finally{this.busy=false;this.render(true);}
  }
  draw(history){
    this.resize?.disconnect();const canvas=this.shadowRoot.querySelector('canvas');if(!canvas)return;
    const paint=()=>{
      const ctx=canvas.getContext('2d'),width=canvas.clientWidth,height=260,ratio=devicePixelRatio||1;
      canvas.width=width*ratio;canvas.height=height*ratio;ctx.scale(ratio,ratio);ctx.clearRect(0,0,width,height);
      const samples=history.samples;if(!samples.length)return;
      const values=samples.flatMap(s=>Object.values(s.channels).flatMap(c=>[c.temperature,c.ambient]).filter(Number.isFinite));
      if(!values.length){ctx.fillStyle=getComputedStyle(this).getPropertyValue('--secondary-text-color')||'#777';ctx.fillText(this.t('No recent readings recorded','Nessuna lettura recente registrata'),20,40);return;}
      const min=Math.floor(values.reduce((a,b)=>Math.min(a,b),Infinity)/10)*10,max=Math.max(min+10,Math.ceil(values.reduce((a,b)=>Math.max(a,b),-Infinity)/10)*10),left=42,right=12,top=16,bottom=30;
      const first=samples[0].at,last=Math.max(first+1,samples.at(-1).at),x=t=>left+(t-first)/(last-first)*(width-left-right),y=v=>top+(max-v)/(max-min)*(height-top-bottom);
      ctx.font='11px system-ui';ctx.fillStyle=getComputedStyle(this).getPropertyValue('--secondary-text-color')||'#777';
      for(let i=0;i<=4;i++){const v=min+(max-min)*i/4;ctx.fillText(`${v.toFixed(0)} C`,1,y(v)+4);ctx.strokeStyle='#8884';ctx.beginPath();ctx.moveTo(left,y(v));ctx.lineTo(width-right,y(v));ctx.stroke();}
      ctx.fillText(new Date(first*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}),left,height-6);ctx.fillText(new Date(last*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}),Math.max(left,width-60),height-6);
      history.summary.layout.forEach((channel,i)=>{for(const field of ['temperature','ambient']){ctx.strokeStyle=['#168b89','#e38b19','#ca4a72','#6476d2'][i];ctx.lineWidth=2;ctx.setLineDash(field==='ambient'?[4,4]:[]);ctx.beginPath();let previous=null;for(const p of series(history,channel.id,field)){if(p.y===null){previous=null;continue;}if(previous===null||p.x-previous>90)ctx.moveTo(x(p.x),y(p.y));else ctx.lineTo(x(p.x),y(p.y));previous=p.x;}ctx.stroke();}});
    };this.resize=new ResizeObserver(paint);this.resize.observe(canvas);paint();
  }
}
if(!customElements.get('inkbird-cook-panel'))customElements.define('inkbird-cook-panel',CookPanel);
