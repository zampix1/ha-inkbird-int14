import './inkbird-cook-panel.js?v=1.2.0-release.1';

class InkbirdIntCookControl extends HTMLElement {
  static getCreateSuggestions(){return {title:'Inkbird Cook Control',icon:'mdi:grill'};}
  static shouldRegenerate(config,oldHass,newHass){return oldHass.states['input_select.bbq_language']?.state!==newHass.states['input_select.bbq_language']?.state;}
  static async generate(config,hass){
    const it=hass.states['input_select.bbq_language']?.state==='Italiano';
    return {title:'Cook Control',views:[
      {title:it?'Cotture':'Cooks',path:'cook',type:'panel',icon:'mdi:grill',cards:[{type:'custom:inkbird-cook-card'}]},
      {title:it?'Storico':'History',path:'history',type:'panel',icon:'mdi:chart-timeline-variant',cards:[{type:'custom:inkbird-cook-card',history:true}]},
      {title:it?'Impostazioni':'Settings',path:'settings',icon:'mdi:cog-outline',cards:[
        {type:'entities',title:it?'Annunci Echo e avvisi TV':'Echo announcements and TV notifications',entities:[
          'input_select.bbq_language','input_text.bbq_notify_service','input_select.bbq_notify_target',
          'input_boolean.bbq_tts_alerts','input_select.bbq_tts_engine','input_select.bbq_tts_speaker',
          'input_text.bbq_alexa_group_name','input_text.bbq_alexa_group_targets',
          'input_boolean.bbq_tv_alerts','input_text.bbq_tv_notify_service','input_text.bbq_tv_entity',
          'input_number.bbq_snooze_minutes','input_number.bbq_rest_minutes',
          'input_boolean.bbq_battery_alerts','input_number.bbq_battery_threshold','input_boolean.bbq_stall_alerts',
          'input_text.bbq_custom_name','input_number.bbq_custom_target',
        ]},
        {type:'button',name:it?'Prova Echo e TV':'Test Echo and TV',icon:'mdi:bullhorn-outline',tap_action:{action:'perform-action',perform_action:'script.bbq_notify',data:{
          title:'Cook Control',message:it?'Prova avvisi, nessuna cottura.':'Notification test, no cook.',tts_message:it?'Prova Cook Control. Gli annunci funzionano.':'Cook Control test. Announcements are working.',tag:'cook_control_test',
        }}},
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
