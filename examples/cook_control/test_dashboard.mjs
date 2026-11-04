import assert from 'node:assert/strict';

const registry = new Map();
globalThis.HTMLElement = class {};
globalThis.customElements = {get:name=>registry.get(name),define:(name,cls)=>registry.set(name,cls)};
globalThis.window = {};
await import('./www/inkbird-int/inkbird-int-cook-control.js');
const Strategy = registry.get('ll-strategy-dashboard-inkbird-int-cook-control');
const prefix = 'sensor.test_inkbird';
const config = {prefix,model:'int14_bw'};
const states = {'input_text.inkbird_sensor_prefix':{state:prefix}, 'input_select.bbq_language':{state:'English'}};
for (let n=1;n<=4;n++) for (const channel of ['internal','ambient']) {
  states[`${prefix}_probe_${n}_${channel}_temperature`] = {state:'22',attributes:{unit_of_measurement:'\u00b0C'}};
}
const result = await Strategy.generate(config,{states});
assert.equal(result.inkbird_model,'int14_bw');
const probes = JSON.stringify(result.views.find(v=>v.path==='probes'));
assert.doesNotMatch(probes,/food_[1-4]_temperature|picture-elements/);
for (const id of Object.keys(states).filter(id=>id.startsWith(prefix))) assert.ok(probes.includes(id));
function styleCheck(node) {
  if (!node || typeof node !== 'object') return;
  if (node.styles) for (const [key,value] of Object.entries(node.styles)) {
    for (const rules of key === 'custom_fields' ? Object.values(value) : [value]) {
      assert.ok(Array.isArray(rules));
      assert.ok(rules.every(rule=>rule && typeof rule === 'object' && !Array.isArray(rule)));
    }
  }
  Object.values(node).forEach(styleCheck);
}
styleCheck(result);
await assert.rejects(Strategy.generate({...config,model:'int14s_bw'},{states}),/requires/);
await assert.rejects(Strategy.generate({...config,prefix:'invalid'},{states}),/requires/);
await assert.rejects(Strategy.generate(config,{states:{}}),/YAML package/);
await assert.rejects(Strategy.generate(config,{states:{'input_text.inkbird_sensor_prefix':{state:prefix}}}),/eight/);
await assert.rejects(Strategy.generate(config,{states:{...states,[`${prefix}_configured_model_profile`]:{state:'int14s_bw'}}}),/Only/);
assert.equal(registry.has('ll-strategy-dashboard-inkbird-bbq'),false);
console.log('Cook Control preview: 8 channels, valid styles, model guards and isolated strategy registration passed.');
const detected = {...states, [`${prefix}_configured_model_profile`]:{state:'int14_bw'}};
assert.equal((await Strategy.generate({}, {states:detected})).inkbird_model,'int14_bw');
detected['input_text.inkbird_sensor_prefix'] = {state:''};
const setup = await Strategy.generate({}, {states:detected});
assert.equal(setup.views[0].path,'setup');
assert.equal(setup.views[0].cards[1].tap_action.data.prefix,prefix);
assert.equal(setup.views[0].cards[1].tap_action.perform_action,'script.bbq_select_thermometer');
assert.ok(Strategy.shouldRegenerate({}, {states}, {states:{...states,'input_select.bbq_language':{state:'Italiano'}}}));
const {connection,renderDiagram,renderHeader} = window.InkbirdIntCookControl;
const now = Date.now();
const recent = {...states,[`${prefix}_last_ble_update_epoch`]:{state:String(now/1000-10)}};
assert.equal(connection(recent,prefix,now).fresh,true);
assert.equal(connection({...recent,[`${prefix}_last_ble_update_epoch`]:{state:String(now/1000-121)}},prefix,now).fresh,false);
assert.equal(connection({...states,[`${prefix}_last_cloud_update_epoch`]:{state:String(now/1000)}},prefix,now).fresh,false);
assert.equal((renderDiagram(recent,prefix,1).match(/<circle /g)||[]).length,2);
assert.match(renderHeader(recent,prefix,1),/Alerts off/);
assert.match(renderHeader({...recent,'input_select.bbq_language':{state:'Italiano'}},prefix,1),/Avvisi disattivati/);
console.log('One-time setup, language regeneration, freshness and two-sensor diagram passed.');

const ip = 'sensor.test_iht';
const iht = {'input_text.inkbird_sensor_prefix':{state:ip},'input_select.bbq_language':{state:'Italiano'},[`${ip}_last_update_epoch`]:{state:String(now/1000-6)},[`${ip}_battery_raw_level`]:{state:'2'}};
for (const ch of ['built_in','external_1','external_2']) iht[`${ip}_${ch}_temperature`] = {state:ch === 'external_1' ? 'unknown' : '123.4',attributes:{unit_of_measurement:'\u00b0C'}};
const ih = await Strategy.generate({}, {states:iht});
assert.equal(ih.inkbird_model,'iht2pb');
const {devices,channelEntity,renderSide,renderConnection} = window.InkbirdIntCookControl;
assert.equal(channelEntity(iht,ip,1),`${ip}_built_in_temperature`);
assert.equal(channelEntity(iht,ip,2),`${ip}_external_1_temperature`);
assert.equal(channelEntity(iht,ip,3),`${ip}_external_2_temperature`);
assert.equal(channelEntity(iht,ip,4),null);
assert.equal(connection(iht,ip,now).fresh,true);
assert.equal(connection({...iht,[`${ip}_last_update_epoch`]:{state:String(now/1000-150)}},ip,now).fresh,false);
assert.equal(connection({...iht,[`${ip}_last_update_epoch`]:{state:'unknown'},[`${ip}_last_cloud_update_epoch`]:{state:String(now/1000)}},ip,now).fresh,false);
assert.equal(ih.views.find(v=>v.path==='probes').sections.length,3);
const serialized = JSON.stringify(ih.views);
assert.doesNotMatch(serialized,/_ambient_temperature|_probe_4_|test_iht_base_|test_iht_probe_[1-4]_/);
assert.match(serialized,/_external_2_temperature/);
assert.doesNotMatch(renderSide(iht,ip,3,now),/Ambiente|Station/);
assert.match(renderConnection(iht,ip,now),/Livello batteria \(non %\): 2/);
assert.equal((renderDiagram(iht,ip,3).match(/<circle /g)||[]).length,1);
const multi = {...states,...iht,[`${prefix}_configured_model_profile`]:{state:'int14_bw'}};
assert.equal(devices(multi).length,2);
const hiddenDiagnostic = {...multi};
delete hiddenDiagnostic[`${prefix}_configured_model_profile`];
assert.equal(devices(hiddenDiagnostic).length,2, 'Disabled diagnostic entity must not hide the INT station');
const selected = await Strategy.generate({}, {states:multi});
assert.equal((await Strategy.generate({prefix,model:'int14_bw'}, {states:multi})).inkbird_model,'iht2pb', 'Selected thermometer must override an old initial prefix');
const selector = selected.views.find(v=>v.path==='cook').sections[0].cards.find(c=>c.title==='Termometro');
assert.equal(selector.cards.length,2);
assert.equal(selector.cards.find(c=>c.tap_action.action==='perform-action').tap_action.data.prefix,prefix);
assert.ok(selector.cards.find(c=>c.tap_action.action==='perform-action').tap_action.confirmation);
assert.equal(devices({...multi,[`${prefix}_configured_model_profile`]:{state:'int14s_bw'}}).length,1);
styleCheck(ih);
assert.match(window.InkbirdIntCookControl.renderGauge(iht,ip,3),/Nessuna soglia/);
assert.doesNotMatch(window.InkbirdIntCookControl.renderGauge(iht,ip,3),/target 0/);
console.log('IHT mapping, three channels, raw battery, freshness and guarded thermometer selection passed.');

const second = 'sensor.test_iht_second';
const duplicates = {...multi,[`${ip}_device_name`]:{state:'My IHT'},[`${second}_device_name`]:{state:'My IHT'}};
for (const ch of ['built_in','external_1','external_2']) duplicates[`${second}_${ch}_temperature`] = {state:'unavailable'};
const choices = devices(duplicates);
assert.equal(choices.length,3);
assert.equal(new Set(choices.map(d=>d.name)).size,3,'Identical device names must still be distinguishable');
const currentButton = window.InkbirdIntCookControl.devicePicker(duplicates).cards.find(c=>c.icon==='mdi:thermometer-check');
assert.equal(currentButton.tap_action.action,'none');
assert.ok(Strategy.shouldRegenerate({}, {states:multi}, {states:duplicates}));
const copy = structuredClone(duplicates);
await Strategy.generate({}, {states:duplicates});
assert.deepEqual(duplicates,copy,'Opening the dashboard must never mutate source states or helpers');
console.log('Duplicate model names, disabled current selector and read-only generation passed.');
