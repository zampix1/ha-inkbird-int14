import './inkbird-cook-panel.js?v=1.2.1';

class InkbirdIntCookControl extends HTMLElement {
  static getCreateSuggestions(){return {title:'Inkbird Cook Control',icon:'mdi:grill'};}
  static shouldRegenerate(config,oldHass,newHass){return oldHass.states['input_select.bbq_language']?.state!==newHass.states['input_select.bbq_language']?.state;}
  static async generate(config,hass){
    const it=hass.states['input_select.bbq_language']?.state==='Italiano';
    return {title:'Cook Control',views:[
      {title:it?'Cotture':'Cooks',path:'cook',type:'panel',icon:'mdi:grill',cards:[{type:'custom:inkbird-cook-card'}]},
      {title:it?'Sonde e termometro':'Probes and device',path:'probes',type:'panel',icon:'mdi:thermometer-probe',cards:[{type:'custom:inkbird-cook-card',device:true}]},
      {title:it?'Storico':'History',path:'history',type:'panel',icon:'mdi:chart-timeline-variant',cards:[{type:'custom:inkbird-cook-card',history:true}]},
      {title:it?'Impostazioni':'Settings',path:'settings',icon:'mdi:cog-outline',cards:[
        {type:'entities',show_header_toggle:false,title:it?'Annunci Echo e avvisi TV':'Echo announcements and TV notifications',entities:[
          'input_select.bbq_language','input_text.bbq_notify_service','input_select.bbq_notify_target',
          'input_boolean.bbq_tts_alerts','input_select.bbq_tts_engine','input_select.bbq_tts_speaker',
          'input_text.bbq_alexa_group_name','input_text.bbq_alexa_group_targets',
          'input_boolean.bbq_tv_alerts','input_text.bbq_tv_notify_service','input_text.bbq_tv_entity',
        ]},
        {type:'entities',show_header_toggle:false,title:it?'Valori predefiniti degli avvisi':'Alert defaults',entities:[
          'input_number.bbq_snooze_minutes','input_number.bbq_rest_minutes',
          'input_boolean.bbq_battery_alerts','input_number.bbq_battery_threshold','input_boolean.bbq_stall_alerts',
        ]},
        {type:'entities',show_header_toggle:false,title:it?'Visualizzazione':'Display',entities:[
          'input_select.inkbird_unit','input_select.bbq_accent','input_select.bbq_style','input_number.bbq_graph_max',
        ]},
        {type:'button',name:it?'Aggiorna lista speaker':'Refresh speaker list',icon:'mdi:refresh',tap_action:{action:'perform-action',perform_action:'script.bbq_refresh_media_targets'}},
        {type:'custom:inkbird-cook-card',test:true},
      ]},
    ]};
  }
}
// A new strategy identity cannot reuse a cached single-cook constructor.
customElements.define('ll-strategy-dashboard-inkbird-cook-control',InkbirdIntCookControl);
if(!customElements.get('ll-strategy-dashboard-inkbird-int-cook-control')){
  customElements.define('ll-strategy-dashboard-inkbird-int-cook-control',class extends InkbirdIntCookControl{});
}
window.customStrategies=window.customStrategies||[];
window.customStrategies.push({type:'inkbird-cook-control',strategyType:'dashboard',name:'Cook Control',description:'Independent cooks, local history and Echo/TV alerts',documentationURL:'https://github.com/zampix1/ha-inkbird-int14/tree/main/examples/cook_control'});
