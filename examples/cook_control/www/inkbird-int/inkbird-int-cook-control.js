import './cook-base-v1.4.3.js?v=1';
import * as presentation from './inkbird-int-cook-model.mjs?v=1.1.0';

window.InkbirdIntCookControl = Object.freeze({...presentation});
const Base = customElements.get('ll-strategy-dashboard-inkbird-int-cook-base');

class InkbirdIntCookControl extends HTMLElement {
  static getCreateSuggestions() { return {title:'Inkbird Cook Control',icon:'mdi:grill'}; }
  static shouldRegenerate(config, oldHass, newHass) {
    return ['input_text.inkbird_sensor_prefix','input_select.bbq_language'].some(
      id => oldHass.states[id]?.state !== newHass.states[id]?.state)
      || presentation.devices(oldHass.states).map(d => d.prefix).join() !== presentation.devices(newHass.states).map(d => d.prefix).join();
  }
  static async generate(config, hass) {
    if (!hass.states['input_text.inkbird_sensor_prefix']) {
      throw new Error('Install the Cook Control YAML package and restart Home Assistant before opening this dashboard.');
    }
    const configured = hass.states['input_text.inkbird_sensor_prefix']?.state;
    if ((config.model && !['int14_bw','iht2pb'].includes(config.model)) || (config.prefix && !/^sensor\.[a-z0-9_]+$/.test(config.prefix))) {
      throw new Error('Cook Control requires an INT-14-BW or IHT-2PB with a valid sensor prefix.');
    }
    const choices = presentation.devices(hass.states);
    const prefix = choices.some(d => d.prefix === configured) ? configured : config.prefix || (choices.length === 1 ? choices[0].prefix : '');
    const actual = hass.states[`${prefix}_configured_model_profile`]?.state;
    if (actual && !['unknown','unavailable','int14_bw'].includes(actual)) throw new Error('Only INT-14-BW and IHT-2PB are mapped by this Cook Control version.');
    if (config.prefix && !presentation.model(hass.states,prefix)) throw new Error('Expected the eight INT-14-BW channels or the three IHT-2PB channels. Check entity availability.');
    const model = presentation.model(hass.states, prefix);
    config = {...config, prefix, model, language:hass.states['input_select.bbq_language']?.state === 'Italiano' ? 'it' : 'en'};
    if (configured !== prefix || !model) {
      const it = config.language === 'it';
      return {title:'Cook Control',views:[{title:it ? 'Termometro' : 'Thermometer',path:'setup',cards:[
        {type:'markdown',content:it ? '## Scegli il termometro' : '## Choose a thermometer'},
        ...presentation.devicePicker(hass.states).cards,
        {type:'entities',entities:['input_select.bbq_language']},
      ]}]};
    }
    // Reuse the presentation templates; IHT channels are mapped explicitly below.
    return presentation.adapt(await Base.generate({...config,model:'int14_bw'}, hass), config, hass.states);
  }
}

customElements.define('ll-strategy-dashboard-inkbird-int-cook-control', InkbirdIntCookControl);
window.customStrategies = window.customStrategies || [];
window.customStrategies.push({type:'inkbird-int-cook-control',strategyType:'dashboard',name:'Inkbird Cook Control',description:'INT-14-BW and IHT-2PB: temperatures and cooking alerts',documentationURL:'https://github.com/zampix1/ha-inkbird-int14/blob/main/examples/cook_control/README.md'});
