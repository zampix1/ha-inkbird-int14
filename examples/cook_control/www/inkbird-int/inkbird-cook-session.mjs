export const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const selectedDevice = (devices, selected) => devices.find(d => d.id === selected) || devices[0];
export const displayTemperature = (value,unit='C') => unit==='F'?value*9/5+32:value;
export const celsiusTemperature = (value,unit='C') => unit==='F'?(value-32)*5/9:value;
export const formatTemperature = (value,unit='C') => Number.isFinite(value) ? `${displayTemperature(value,unit).toFixed(1)}\u00b0${unit}` : '\u2014';
export function csv(history) {
  const quote = value => `"${String(value ?? '').replace(/"/g, '""')}"`;
  const rows = [['time_utc','channel','temperature_c','ambient_c','target_c','armed','battery_percent']];
  for (const sample of history.samples) for (const [id, channel] of Object.entries(sample.channels)) {
    rows.push([new Date(sample.at * 1000).toISOString(), id, channel.temperature, channel.ambient, channel.target, channel.armed, channel.battery]);
  }
  return rows.map(row => row.map(quote).join(',')).join('\r\n');
}
export async function loadHistory(call, sessionId) {
  const result = {samples:[]};
  let offset = 0;
  let limit;
  do {
    const page = await call('history', {session_id:sessionId, offset,...(limit===undefined?{}:{limit})});
    if(offset===0){result.summary=page.summary;result.events=page.events;limit=page.total_samples;}
    result.samples.push(...page.samples);
    offset = page.next_offset;
  } while (offset !== null);
  return result;
}

export function series(history, channel, field = 'temperature') {
  return history.samples.map(sample => ({x:sample.at,y:sample.channels[channel]?.[field] ?? null}));
}
