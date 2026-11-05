import {escape as e, selectedDevice, formatTemperature as temp,displayTemperature,celsiusTemperature,csv,loadHistory,series} from './inkbird-cook-session.mjs?v=1.2.1';
import {probeColor,probeFigure,dial,sparkline} from './inkbird-cook-visuals.mjs?v=1.2.1';

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
.delivery{display:grid;gap:5px;margin:8px 0;font-size:12px}.delivery .failed{color:var(--error-color,#b32b2b)}.device-detail{padding:20px 0;border-bottom:1px solid var(--divider-color)}.native-device{margin:16px 0}.stall-progress{font-size:12px;margin:6px 0}.alarm-options{margin-top:12px;border-top:1px solid var(--divider-color);padding-top:10px}.alarm-options summary{min-height:32px;cursor:pointer}.alarm-options .settings{margin-top:10px}
@media(max-width:760px){.grid{grid-template-columns:minmax(0,1fr)}}
@media(max-width:550px){h1{font-size:22px}.history th:nth-child(3),.history td:nth-child(3){display:none}.session button{flex:1}.grid{gap:10px}article{padding:14px}.instrument{grid-template-columns:26px 128px minmax(0,1fr);gap:9px}.dial{width:124px;height:124px}.metrics{font-size:13px;gap:6px}}
@media(max-width:360px){:host{padding-left:10px;padding-right:10px}.instrument{grid-template-columns:24px 120px minmax(0,1fr);gap:6px}.dial{width:116px;height:116px}.metrics div{display:block}.metrics b{display:block}}
`;

class CookPanel extends HTMLElement {
  constructor(){super();this.attachShadow({mode:'open'});this.data={devices:[],history:[]};this.view='';this.error='';this.busy=false;this.alive=false;this.cookDrafts={};}
  setConfig(config){this.config=config;this.render();}
  set hass(value){this._hass=value;const language=value.states['input_select.bbq_language']?.state,backend=value.states['sensor.inkbird_cook_control']?.state;const prefs=['input_select.inkbird_unit','input_select.bbq_accent','input_select.bbq_style','input_number.bbq_graph_max'].map(k=>value.states[k]?.state).join('|');if(language!==this.language||backend!==this.backendStatus||prefs!==this.prefs){this.language=language;this.backendStatus=backend;this.prefs=prefs;this.render();}if(this.isConnected)this.connect();}
  getCardSize(){return 8;}
  connectedCallback(){this.alive=true;this.connect();this.clock=setInterval(()=>this.render(),5000);}
  disconnectedCallback(){this.alive=false;this.unsubscribe?.();this.unsubscribe=null;this.connection=null;this.resize?.disconnect();clearInterval(this.clock);}
  t(en,it){return this.language==='Italiano'?it:en;}
  get unit(){return this._hass?.states['input_select.inkbird_unit']?.state?.includes('F')?'F':'C';}
  temp(value){return temp(value,this.unit);}
  effective(c){return {...c,fresh:c.fresh&&(!c.epoch||Date.now()/1000-c.epoch<=120)};}
  async connect(){
    if(!this._hass||this.connection===this._hass.connection)return;
    this.unsubscribe?.();this.connection=this._hass.connection;
    try{
      const unsubscribe=await this.connection.subscribeMessage(data=>{this.data=data;this.render();const row=data.history.find(r=>r.id===this.historyId);if(row&&this.history&&`${row.sample_count}:${row.ended}`!==this.historyStamp)this.refreshHistory();},{type:'inkbird_cook_control/subscribe'});
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
    if(!this.config)return;
    const d=this.selected();
    if(!force&&this.shadowRoot.activeElement?.matches('input:not([type=checkbox]),select')){if(d)this.refreshLive(d);return;}
    if(!force&&this.config.device&&d?.id===this.renderedDevice&&this.shadowRoot.querySelector('.native-device')){this.refreshLive(d);this.shadowRoot.querySelectorAll('hui-entities-card').forEach(card=>{card.hass=this._hass;});return;}
    this.renderedDevice=d?.id;
    this.openCards=new Set([...this.shadowRoot.querySelectorAll('details[open]')].map(el=>`${el.closest('[data-channel]')?.dataset.channel}:${el.dataset.section}`));
    this.shadowRoot.innerHTML=`<style>${style}</style><header><h1>Cook Control</h1><ha-icon icon="mdi:grill"></ha-icon></header>
      <div id="live-error">${this.error?`<div class="error" role="alert">${e(this.error)}</div>`:''}</div>
      ${this.backendStatus!=='active'?`<div class="error" role="alert">${this.t('Cook Control backend is not active. Alerts are not being processed.','Il backend Cook Control non e attivo. Gli avvisi non vengono elaborati.')}</div>`:''}
      ${this.config.test?this.renderTests():this.config.history?this.renderHistory():d?this.config.device?this.renderDevice(d):this.renderCook(d):`<p>${this.t('Waiting for registered INT-14-BW and IHT-2PB thermometers.','In attesa dei termometri INT-14-BW e IHT-2PB registrati.')}</p>`}`;
    const transparent=this._hass?.states['input_select.bbq_style']?.state==='Transparent';
    if(transparent)this.shadowRoot.querySelectorAll('article').forEach(el=>el.style.background='transparent');
    this.accent=({Ember:'#b85a27',Blue:'#2f7ce0',Green:'#34b56a',Purple:'#8a5cf0',Red:'#e0483a',Teal:'#1fb6b0'})[this._hass?.states['input_select.bbq_accent']?.state]||'#b85a27';
    this.bind(d);
    if(d)this.decorateLive(d);
    if(this.config.device&&d)this.mountNative(d);
    if(this.config.history&&this.history)this.draw(this.history);
    else if(d?.recent?.length)this.draw({summary:{layout:d.layout},samples:d.recent});
  }
  renderCook(d){
    const armed=device=>Object.values(device.channels).filter(c=>c.armed).length;
    return `<div class="overview">${this.data.devices.map(device=>`<button class="${device.id===d.id?'chosen':''}" data-view="${e(device.id)}">${e(device.alias)}<br><small>${armed(device)} ${armed(device)===1?this.t('alert on','avviso attivo'):this.t('alerts on','avvisi attivi')}</small></button>`).join('')}</div>
      <div class="toolbar"><select aria-label="${this.t('Thermometer','Termometro')}" id="device">${this.data.devices.map(device=>`<option value="${e(device.id)}" ${device.id===d.id?'selected':''}>${e(device.alias)}</option>`).join('')}</select><button class="icon" id="rename" title="${this.t('Rename thermometer','Rinomina termometro')}"><ha-icon icon="mdi:pencil-outline"></ha-icon></button></div>
      <div class="muted">${e(d.name)} &middot; ${d.model==='int14_bw'?'INT-14-BW &middot; 4 '+this.t('probes, food + ambient','sonde, cuore + ambiente'):'IHT-2PB &middot; '+this.t('built-in tip and 2 external probes','punta integrata e 2 sonde esterne')}</div>
      <div class="connection-live">${this.renderConnection(d)}</div>
      <div class="session">${d.cook?`<div><h2>${e(d.cook.name)}</h2><small>${new Date(d.cook.started*1000).toLocaleString()}</small></div><button id="finish"><ha-icon icon="mdi:stop-circle-outline"></ha-icon> ${this.t('Finish cook','Termina cottura')}</button>`:`<label class="field">${this.t('Cook name','Nome cottura')}<input id="cookname" maxlength="100" value="${e(this.cookDrafts[d.id]||'')}" placeholder="${this.t('Sunday BBQ','Grigliata della domenica')}"></label><button id="start" class="primary"><ha-icon icon="mdi:play-outline"></ha-icon> ${this.t('Start recording','Avvia storico')}</button>`}</div>
      <div class="grid">${d.layout.map(layout=>this.renderChannel(d,layout)).join('')}</div>
      ${d.recent?.length?`<h2>${this.t('Recent temperatures','Temperature recenti')}</h2><canvas role="img" aria-label="${this.t('Recent temperature trend','Andamento recente delle temperature')}"></canvas>`:''}`;
  }
  renderConnection(d){
    const epochs=(d.epochs||[]).map(k=>Number(this._hass?.states[k]?.state)).filter(v=>Number.isFinite(v)&&v>0);
    const age=epochs.length?Math.max(0,Math.floor(Date.now()/1000-Math.max(...epochs))):null;
    const transport=(d.inspection||[]).find(k=>k.endsWith('_active_transport'));
    const base=(d.inspection||[]).find(k=>k.endsWith('_base_battery'));
    const raw=d.battery_raw_entity;
    const battery=this._hass?.states[base||raw]?.state;
    const batteryText=battery!==undefined&&battery!==''&&Number.isFinite(Number(battery))?e(battery)+(base?'%':''):'\u2014';
    return `<p class="muted">${e(transport?this._hass.states[transport]?.state||'\u2014':this.t('Bluetooth','Bluetooth'))} &middot; ${age===null?this.t('No local packet','Nessun pacchetto locale'):age+' s '+this.t('ago','fa')}${base||raw?' &middot; '+(base?this.t('Base battery','Batteria base'):this.t('Battery level','Livello batteria'))+': '+batteryText:''}</p>`;
  }
  renderDevice(d){
    return `<div class="toolbar"><select id="device" aria-label="${this.t('Thermometer','Termometro')}">${this.data.devices.map(x=>`<option value="${e(x.id)}" ${x.id===d.id?'selected':''}>${e(x.alias)}</option>`).join('')}</select></div><h2>${e(d.alias)}</h2><div class="connection-live">${this.renderConnection(d)}</div><div class="native-device"></div><div class="grid">${d.layout.map(layout=>`<section class="device-detail" data-channel="${layout.id}"><h3>${e(this.channelName(d,layout,d.channels[layout.id]))}</h3><div class="live">${this.renderLive(d,layout)}</div><div class="native-probe" data-native-channel="${layout.id}"></div></section>`).join('')}</div>`;
  }
  renderTests(){const labels={accepted:this.t('Service accepted','Accettato dal servizio'),queued:this.t('Queued','In coda'),sending:this.t('Sending','Invio'),error:this.t('Error','Errore'),unknown:this.t('Check delivery','Esito da verificare'),disabled:this.t('Disabled','Disattivato'),skipped:this.t('TV off','TV spenta')};return `<h2>${this.t('Test Echo and TV','Prova Echo e TV')}</h2><div class="row">${this.data.devices.map(d=>`<button data-test="${e(d.id)}"><ha-icon icon="mdi:bullhorn-outline"></ha-icon> ${e(d.alias)}</button>`).join('')}</div>${(this.data.tests||[]).slice().reverse().map(test=>`<div class="device-detail"><b>TEST ${e(test.device_name)}</b><div class="delivery">${test.outputs.map(o=>`<div>${e(o.label)}: ${labels[o.state]||e(o.state)}${o.error?' &middot; '+e(o.error):''}</div>`).join('')}</div></div>`).join('')}`;}
  async mountNative(d){
    const helpers=typeof window.loadCardHelpers==='function'?await window.loadCardHelpers():null;
    const mount=(host,entities)=>{if(!host||!host.isConnected||!entities.length)return;const config={type:'entities',show_header_toggle:false,entities};const card=helpers?helpers.createCardElement(config):document.createElement('hui-entities-card');if(!card.setConfig)return;if(!helpers)card.setConfig(config);card.hass=this._hass;host.append(card);};
    mount(this.shadowRoot.querySelector('.native-device'),(d.inspection||[]).filter(k=>this._hass.states[k]));
    for(const layout of d.layout)mount(this.shadowRoot.querySelector(`[data-native-channel="${layout.id}"]`),[layout.entity,layout.ambient_entity,layout.target_entity,layout.battery_entity,...(layout.control_entities||[])].filter(k=>k&&this._hass.states[k]));
  }
  renderLive(d,layout){
    const c=this.effective(d.channels[layout.id]),iht=d.model==='iht2pb',color=probeColor(c);
    const statuses={off:this.t('HA alarm off','Allarme HA spento'),stale:this.t('Waiting for fresh readings','In attesa di letture recenti'),cooking:this.t('HA alarm on','Allarme HA attivo'),ready:this.t('Above target','Sopra soglia'),reached:this.t('Target reached','Soglia raggiunta'),notified:this.t('Target reached','Soglia raggiunta')};
    const status=!c.fresh&&c.armed?statuses.stale:statuses[c.status]||e(c.status);
    const deliveryNames={queued:this.t('Queued','In coda'),sending:this.t('Sending','Invio in corso'),accepted:this.t('Service accepted','Accettato dal servizio'),error:this.t('Error','Errore'),unknown:this.t('Check delivery','Esito da verificare'),disabled:this.t('Disabled','Disattivato'),cancelled:this.t('Cancelled','Annullato'),skipped:this.t('TV off','TV spenta')};
    return `<p class="status">${status}${c.status==='ready'?` &middot; ${Math.min(30,Math.floor(c.ready_seconds))}/30 s`:''}</p><div class="instrument">${probeFigure(d.model,layout.id,color)}${dial(c,{target:this.t('target','soglia'),noTarget:this.t('No target','Nessuna soglia')},this.unit)}<div class="metrics">${!iht?`<div><span>${this.t('Ambient','Ambiente')}</span><b>${this.temp(c.ambient)}</b></div>`:''}<div><span>${this.t('HA target','Soglia HA')}</span><b>${c.target>0?this.temp(c.target):'\u2014'}</b></div><div><span>${this.t('Device alarm','Allarme termometro')}</span><b>${this.temp(c.device_target)}</b></div><div><span>${this.t('Battery','Batteria')}</span><b>${Number.isFinite(c.battery)?c.battery+'%':Number.isFinite(c.battery_raw)?this.t('level','livello')+' '+c.battery_raw:'\u2014'}</b></div>${c.battery_suspect?`<small>${this.t('Suspect battery report','Dato batteria sospetto')}</small>`:''}<small>${c.fresh?this.t('Recent reading','Lettura recente'):this.t('No recent reading','Nessuna lettura recente')}</small></div></div>${sparkline(d.recent||[],layout.id,this.accent||color,this.t('Temperature trend','Andamento temperatura'))}<div class="delivery">${(c.delivery||[]).map(output=>`<div class="row ${['error','unknown'].includes(output.state)?'failed':''}"><span>${e(output.label)}: ${deliveryNames[output.state]||e(output.state)}${output.error?' &middot; '+e(output.error):''}</span>${['error','unknown'].includes(output.state)?`<button class="icon" data-retry="${e(c.notice_id)}" data-output="${e(output.id)}" title="${this.t('Retry this output only','Riprova solo questa uscita')}"><ha-icon icon="mdi:refresh"></ha-icon></button>`:''}</div>`).join('')}</div>${c.stall_progress?.tracking?`<p class="stall-progress">${this.t('Stall observation','Verifica stallo')}: ${Math.floor(c.stall_progress.elapsed/60)} / ${c.stall?.minutes||45} min</p>`:''}${c.reached||c.status==='notified'?`<div class="row"><button data-reminder="snooze"><ha-icon icon="mdi:alarm-snooze"></ha-icon> Snooze</button><button data-reminder="rest"><ha-icon icon="mdi:timer-outline"></ha-icon> ${this.t('Rest','Riposo')}</button><button class="icon" data-reminder="dismiss" title="${this.t('Cancel reminders','Annulla promemoria')}"><ha-icon icon="mdi:bell-off-outline"></ha-icon></button></div>`:''}${c.snooze||c.rest?`<small>${this.t('Reminder','Promemoria')}: ${new Date((c.snooze||c.rest)*1000).toLocaleTimeString()}</small>`:''}`;
  }
  refreshLive(d){
    for(const layout of d.layout){const article=this.shadowRoot.querySelector(`[data-channel="${layout.id}"]`);const host=article?.querySelector('.live');if(host){host.innerHTML=this.renderLive(d,layout);article.style.setProperty('--probe-color',probeColor(this.effective(d.channels[layout.id])));}}
    const connection=this.shadowRoot.querySelector('.connection-live');if(connection)connection.innerHTML=this.renderConnection(d);
    const error=this.shadowRoot.querySelector('#live-error');if(error)error.innerHTML=this.error?`<div class="error" role="alert">${e(this.error)}</div>`:'';
    this.decorateLive(d);
    this.bindLive(d);
    this.shadowRoot.querySelectorAll('[data-test]').forEach(el=>el.onclick=()=>this.act('test',{device_id:el.dataset.test}));
    if(!this.config.history&&d.recent?.length)this.draw({summary:{layout:d.layout},samples:d.recent});
  }
  decorateLive(d){
    for(const layout of d.layout){const c=this.effective(d.channels[layout.id]);const host=this.shadowRoot.querySelector(`[data-channel="${layout.id}"] .metrics`);if(host&&c.fresh&&Number.isFinite(c.rate)&&!host.querySelector('.rate')){const row=document.createElement('div');row.className='rate';row.innerHTML=`<span>${this.t('Trend','Variazione')}</span><b>${c.rate>0?'+':''}${(c.rate*(this.unit==='F'?1.8:1)).toFixed(1)} \u00b0${this.unit}/h</b>`;host.append(row);}
      const progress=c.stall_progress;const article=this.shadowRoot.querySelector(`[data-channel="${layout.id}"]`);if(progress&&!progress.tracking&&c.armed&&article){const reasons={disabled:this.t('Stall off','Stallo disattivato'),stale:this.t('Stall waiting for readings','Stallo in attesa di letture'),below_minimum:this.t('Below stall minimum temperature','Sotto la temperatura minima di stallo'),above_target:this.t('Stall excluded above target','Stallo escluso sopra soglia')};if(reasons[progress.reason]){const label=document.createElement('p');label.className='stall-progress';label.textContent=reasons[progress.reason];article.querySelector('.live')?.append(label);}}
    }
  }
  renderChannel(d,layout){
    const c=d.channels[layout.id],name=this.channelName(d,layout,c);
    const iht=d.model==='iht2pb',color=probeColor(c),editing=this.customEditor?.device===d.id&&this.customEditor?.channel===layout.id;
    return `<article data-channel="${layout.id}" class="probe-card ${c.fresh?'':'stale'}" style="--probe-color:${color}"><div class="split"><h3><span class="probe-tag">${iht?e(layout.name):'P'+layout.id}</span>${e(name===layout.name?'':name)}</h3><ha-icon icon="mdi:thermometer-probe"></ha-icon></div>
      <div class="live">${this.renderLive(d,layout)}</div>
      <div class="split"><label>${this.t('HA target','Soglia HA')} <input data-setting="target" type="number" min="0" max="${this.unit==='F'?662:350}" step="0.1" value="${c.target>0?displayTemperature(c.target,this.unit).toFixed(1):0}" aria-label="${this.t('HA target','Soglia HA')}"> \u00b0${this.unit}</label><label title="${this.t('Home Assistant alerts, not the device buzzer','Avvisi Home Assistant, non il cicalino del termometro')}"><input data-setting="armed" type="checkbox" ${c.armed?'checked':''} ${this.busy?'disabled':''}>${this.t('HA alarm','Allarme HA')}</label></div>
      <details class="probe-settings" data-section="name" ${this.openCards?.has(layout.id+':name')||editing?'open':''}><summary>${this.t('Name and presets','Nome e preset')}</summary><div class="settings"><label class="field">${this.t('Food / probe name','Pietanza / nome sonda')}<input data-setting="name" value="${e(c.name===layout.name?name:c.name)}" maxlength="100"></label>
      <select data-preset aria-label="Preset"><option value="">${this.t('Preset','Preset')}</option>${[['Beef Brisket',93],['Chicken',74],['Medium Steak',57],['Pork Ribs',90],['Salmon',52]].map(([label,value])=>`<option value="${label}|${value}">${label} &middot; ${this.temp(value)}</option>`).join('')}<option value="custom">${this.t('My preset','Il mio preset')}</option></select>
      ${editing?this.renderCustomPreset():''}</div></details>${this.renderAlarmOptions(c,layout.id)}</article>`;
  }
  renderAlarmOptions(c,id){const rule=c.stall||{enabled:null,minutes:45,rate:1,min_temp:40};return `<details class="alarm-options" data-section="alarms" ${this.openCards?.has(id+':alarms')?'open':''}><summary>${this.t('Stall and rest','Stallo e riposo')}</summary><div class="settings"><label>${this.t('Stall','Stallo')}<select data-stall="enabled"><option value="inherit" ${rule.enabled===null?'selected':''}>${this.t('Global default','Impostazione generale')}</option><option value="on" ${rule.enabled===true?'selected':''}>On</option><option value="off" ${rule.enabled===false?'selected':''}>Off</option></select></label><label>${this.t('Observation','Durata verifica')}<input data-stall="minutes" type="number" min="5" max="180" value="${rule.minutes}"> min</label><label>${this.t('Maximum rise','Variazione massima')}<input data-stall="rate" type="number" min="0.1" max="10" step="0.1" value="${rule.rate}"> \u00b0C/h</label><label>${this.t('Minimum temperature','Temperatura minima')}<input data-stall="min_temp" type="number" min="0" max="150" value="${rule.min_temp}"> \u00b0C</label><label><input data-option="rest_auto" type="checkbox" ${c.rest_auto!==false?'checked':''}>${this.t('Automatic rest reminder','Promemoria riposo automatico')}</label><label>${this.t('Rest duration','Durata riposo')}<input data-option="rest_minutes" type="number" min="0" max="1440" placeholder="${e(this._hass?.states['input_number.bbq_rest_minutes']?.state||'0')}" value="${c.rest_minutes??''}"> min</label></div></details>`;}
  renderCustomPreset(){const draft=this.customEditor.draft;return `<div class="custom-preset"><h3>${this.t('My preset','Il mio preset')}</h3><label class="field">${this.t('Preset name','Nome preset')}<input data-custom="name" value="${e(draft.name)}" maxlength="100"></label><label>${this.t('Temperature','Temperatura')} <input data-custom="target" type="number" min="${this.unit==='F'?32:0.1}" max="${this.unit==='F'?662:350}" step="0.1" value="${displayTemperature(draft.target,this.unit).toFixed(1)}"> \u00b0${this.unit}</label><div class="row"><button data-custom-action="save" title="${this.t('Save preset without changing the cook','Salva il preset senza cambiare la cottura')}"><ha-icon icon="mdi:content-save-outline"></ha-icon> ${this.t('Save','Salva')}</button><button data-custom-action="apply" class="primary">${this.t('Use on this probe','Usa su questa sonda')}</button><button class="icon" data-custom-action="cancel" title="${this.t('Close without applying','Chiudi senza applicare')}"><ha-icon icon="mdi:close"></ha-icon></button></div>${this.presetSaved?`<small>${this.t('Preset saved','Preset salvato')}</small>`:''}</div>`;}
  renderHistory(){
    return `<h2 style="margin-top:20px">${this.t('Cooking history','Storico cotture')}</h2><table class="history"><thead><tr><th>${this.t('Cook','Cottura')}</th><th>${this.t('Thermometer','Termometro')}</th><th>${this.t('Started','Inizio')}</th></tr></thead><tbody>${this.data.history.map(row=>`<tr><td><button data-history="${row.id}">${e(row.name)}${row.ended?'':` &middot; ${this.t('active','in corso')}`}</button></td><td>${e(row.device_name)}</td><td>${new Date(row.started*1000).toLocaleString()}</td></tr>`).join('')}</tbody></table>
      ${this.history?`<div class="split"><h2>${e(this.history.summary.name)}</h2><div class="row"><button data-export="csv"><ha-icon icon="mdi:download"></ha-icon> CSV</button><button data-export="json" title="${this.t('Download full session','Scarica sessione completa')}">JSON</button></div></div><div class="legend">${this.history.summary.layout.map((c,i)=>`<span style="--line:${['#168b89','#e38b19','#ca4a72','#6476d2'][i]}">${e(c.name)}</span>`).join('')}</div><canvas aria-label="${this.t('Recorded temperatures in Celsius','Temperature registrate in gradi Celsius')}" role="img"></canvas><small>${this.t('Solid: food. Dotted: ambient. Gaps: no recent reading.','Linea continua: cuore. Tratteggio: ambiente. Vuoti: nessuna lettura recente.')}</small>
      <h3 style="margin-top:18px">${this.t('Session events','Eventi della cottura')}</h3>${this.history.events.slice(-80).reverse().map(event=>`<div class="event"><small>${new Date(event.at*1000).toLocaleString()}</small> &middot; ${this.eventText(event)}</div>`).join('')}`:`<p class="muted">${this.t('Recordings start when you start a cook or enable its first alert.','La registrazione parte quando avvii una cottura o attivi il primo avviso.')}</p>`}`;
  }
  eventText(event){
    const labels={settings:this.t('Probe settings saved','Impostazioni sonda salvate'),finished:this.t('Cook finished','Cottura terminata'),alert:this.t('Alarm generated','Allarme generato'),notification_result:this.t('Notification result','Esito avviso'),rest:this.t('Rest timer started','Timer riposo avviato'),snooze:this.t('Reminder postponed','Promemoria rinviato'),dismiss:this.t('Reminders cancelled','Promemoria annullati'),reminder_expired:this.t('Reminder expired','Promemoria scaduto')};
    const parts=[labels[event.kind]||event.kind];
    if(event.channel){const layout=this.history?.summary?.layout?.find(c=>c.id===event.channel);parts.push(layout?.name||this.t('Probe','Sonda')+' '+event.channel);}
    if(event.settings){const s=event.settings;if(s.name)parts.push(s.name);if(Number.isFinite(s.target))parts.push(this.t('HA target','Soglia HA')+': '+this.temp(s.target));if(typeof s.armed==='boolean')parts.push(s.armed?this.t('HA alarm on','Allarme HA attivo'):this.t('HA alarm off','Allarme HA spento'));}
    if(event.result)parts.push(event.result);
    return parts.map(e).join(' &middot; ');
  }
  bind(d){
    this.shadowRoot.querySelectorAll('[data-view]').forEach(el=>el.onclick=()=>this.select(el.dataset.view));
    const select=this.shadowRoot.querySelector('#device');if(select)select.onchange=()=>this.select(select.value);
    const rename=this.shadowRoot.querySelector('#rename');if(rename)rename.onclick=()=>{const name=prompt(this.t('Thermometer name','Nome termometro'),d.alias);if(name?.trim())this.act('rename',{device_id:d.id,name});};
    const start=this.shadowRoot.querySelector('#start');if(start)start.onclick=()=>this.act('start',{device_id:d.id,name:this.shadowRoot.querySelector('#cookname').value});
    const cookname=this.shadowRoot.querySelector('#cookname');if(cookname)cookname.oninput=()=>{this.cookDrafts[d.id]=cookname.value;};
    const finish=this.shadowRoot.querySelector('#finish');if(finish)finish.onclick=()=>{if(confirm(this.t('Finish this cook and switch off only its alerts?','Terminare questa cottura e spegnere solo i suoi avvisi?')))this.act('finish',{device_id:d.id});};
    this.shadowRoot.querySelectorAll('[data-setting]').forEach(el=>el.onchange=()=>{const field=el.dataset.setting;this.act('configure',{device_id:d.id,channel:el.closest('[data-channel]').dataset.channel,settings:{[field]:field==='armed'?el.checked:field==='target'?(Number(el.value)===0?0:Math.round(celsiusTemperature(Number(el.value),this.unit)*10)/10):el.value}});});
    this.shadowRoot.querySelectorAll('[data-preset]').forEach(el=>el.onchange=()=>{if(!el.value)return;const channel=el.closest('[data-channel]').dataset.channel;if(el.value==='custom'){const preset=this.data.preset||{name:this._hass.states['input_text.bbq_custom_name']?.state||this.t('Custom','Personalizzato'),target:Number(this._hass.states['input_number.bbq_custom_target']?.state)||60};this.customEditor={device:d.id,channel,draft:{...preset}};this.presetSaved=false;this.render(true);return;}const [name,target]=el.value.split('|');this.act('configure',{device_id:d.id,channel,settings:{name,target:Number(target)}});});
    this.shadowRoot.querySelectorAll('[data-custom]').forEach(el=>el.oninput=()=>{this.customEditor.draft[el.dataset.custom]=el.dataset.custom==='target'?celsiusTemperature(Number(el.value),this.unit):el.value;this.presetSaved=false;});
    this.shadowRoot.querySelectorAll('[data-custom-action]').forEach(el=>el.onclick=()=>this.customPreset(el.dataset.customAction));
    this.shadowRoot.querySelectorAll('[data-stall]').forEach(el=>el.onchange=()=>this.act('configure',{device_id:d.id,channel:el.closest('[data-channel]').dataset.channel,settings:{stall:{[el.dataset.stall]:el.dataset.stall==='enabled'?(el.value==='inherit'?null:el.value==='on'):Number(el.value)}}}));
    this.shadowRoot.querySelectorAll('[data-option]').forEach(el=>el.onchange=()=>this.act('configure',{device_id:d.id,channel:el.closest('[data-channel]').dataset.channel,settings:{[el.dataset.option]:el.type==='checkbox'?el.checked:el.value===''?null:Number(el.value)}}));
    this.bindLive(d);
    this.shadowRoot.querySelectorAll('[data-test]').forEach(el=>el.onclick=()=>this.act('test',{device_id:el.dataset.test}));
    this.shadowRoot.querySelectorAll('[data-history]').forEach(el=>el.onclick=()=>{this.historyId=el.dataset.history;this.history=null;this.refreshHistory();});
    this.shadowRoot.querySelectorAll('[data-export]').forEach(el=>el.onclick=async()=>{try{const history=await loadHistory((...args)=>this.call(...args),this.historyId);const format=el.dataset.export;const blob=new Blob([format==='csv'?csv(history):JSON.stringify(history,null,2)],{type:format==='csv'?'text/csv;charset=utf-8':'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`cook-${history.summary.id}.${format}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(err){this.error=err.message;this.render(true);}});
  }
  bindLive(d){
    this.shadowRoot.querySelectorAll('[data-reminder]').forEach(el=>el.onclick=()=>this.act(el.dataset.reminder,{device_id:d.id,channel:el.closest('[data-channel]').dataset.channel}));
    this.shadowRoot.querySelectorAll('[data-retry]').forEach(el=>el.onclick=()=>{if(confirm(this.t('Retry this output? Check that the previous message did not arrive.','Riprovo questa uscita? Verifica che il messaggio precedente non sia arrivato.')))this.act('retry',{notice_id:el.dataset.retry,output_id:el.dataset.output});});
  }
  async refreshHistory(){
    const id=this.historyId;if(!id||this.historyLoading===id)return;this.historyLoading=id;
    try{const previous=this.history?.summary?.id===id?this.history:null;let result;if(previous){const page=await this.call('history',{session_id:id,offset:previous.samples.length});result={summary:page.summary,events:page.events,samples:[...previous.samples,...page.samples]};if(page.next_offset!==null)result=await loadHistory((...args)=>this.call(...args),id);}else result=await loadHistory((...args)=>this.call(...args),id);if(id!==this.historyId)return;this.history=result;this.historyStamp=`${result.summary.sample_count}:${result.summary.ended}`;this.error='';}catch(err){this.error=err.message;}finally{if(this.historyLoading===id)this.historyLoading=null;this.render(true);}
  }
  async customPreset(action){
    if(action==='cancel'){this.customEditor=null;this.render(true);return;}
    const editor=this.customEditor,draft=editor.draft;
    if(!draft.name.trim()||draft.name.length>100||!Number.isFinite(draft.target)||draft.target<=0||draft.target>350){this.error=this.t('Enter a preset name and a valid temperature.','Inserisci un nome e una temperatura valida.');this.render(true);return;}
    if(action==='apply'){await this.act('configure',{device_id:editor.device,channel:editor.channel,settings:{name:draft.name.trim(),target:draft.target}});if(!this.error)this.customEditor=null;this.render(true);return;}
    this.busy=true;try{this.data=await this.call('preset',{name:draft.name.trim(),target:draft.target});this.presetSaved=true;this.error='';}catch(err){this.error=err.message||String(err);}finally{this.busy=false;this.render(true);}
  }
  draw(history){
    this.resize?.disconnect();const canvas=this.shadowRoot.querySelector('canvas');if(!canvas)return;
    const paint=()=>{
      const ctx=canvas.getContext('2d'),width=canvas.clientWidth,height=260,ratio=devicePixelRatio||1;
      canvas.width=width*ratio;canvas.height=height*ratio;ctx.scale(ratio,ratio);ctx.clearRect(0,0,width,height);
      const samples=history.samples;if(!samples.length)return;
      const values=samples.flatMap(s=>Object.values(s.channels).flatMap(c=>[c.temperature,c.ambient]).filter(Number.isFinite));
      if(!values.length){ctx.fillStyle=getComputedStyle(this).getPropertyValue('--secondary-text-color')||'#777';ctx.fillText(this.t('No recent readings recorded','Nessuna lettura recente registrata'),20,40);return;}
      const graphTop=Number(this._hass?.states['input_number.bbq_graph_max']?.state)||0;
      const min=Math.floor(values.reduce((a,b)=>Math.min(a,b),Infinity)/10)*10,max=Math.max(min+10,graphTop,Math.ceil(values.reduce((a,b)=>Math.max(a,b),-Infinity)/10)*10),left=42,right=12,top=16,bottom=30;
      const first=samples[0].at,last=Math.max(first+1,samples.at(-1).at),x=t=>left+(t-first)/(last-first)*(width-left-right),y=v=>top+(max-v)/(max-min)*(height-top-bottom);
      ctx.font='11px system-ui';ctx.fillStyle=getComputedStyle(this).getPropertyValue('--secondary-text-color')||'#777';
      for(let i=0;i<=4;i++){const v=min+(max-min)*i/4;ctx.fillText(`${displayTemperature(v,this.unit).toFixed(0)} ${this.unit}`,1,y(v)+4);ctx.strokeStyle='#8884';ctx.beginPath();ctx.moveTo(left,y(v));ctx.lineTo(width-right,y(v));ctx.stroke();}
      ctx.fillText(new Date(first*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}),left,height-6);ctx.fillText(new Date(last*1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}),Math.max(left,width-60),height-6);
      history.summary.layout.forEach((channel,i)=>{for(const field of ['temperature','ambient']){ctx.strokeStyle=['#168b89','#e38b19','#ca4a72','#6476d2'][i];ctx.lineWidth=2;ctx.setLineDash(field==='ambient'?[4,4]:[]);ctx.beginPath();let previous=null;for(const p of series(history,channel.id,field)){if(p.y===null){previous=null;continue;}if(previous===null||p.x-previous>90)ctx.moveTo(x(p.x),y(p.y));else ctx.lineTo(x(p.x),y(p.y));previous=p.x;}ctx.stroke();}});
    };this.resize=new ResizeObserver(paint);this.resize.observe(canvas);paint();
  }
}
customElements.define('inkbird-cook-card',CookPanel);
if(!customElements.get('inkbird-cook-panel'))customElements.define('inkbird-cook-panel',class extends CookPanel{});
