export const ROLES = {carer:'照护员', lead:'值班长', receiver:'接班员'};
export const ALERTS = {evaluating:'分级中', incomplete:'待补观察', review:'待复核', confirmed:'已复核', handover:'待接班签收', closed:'已交接'};
export const OBSERVATIONS = {incomplete:'待补', queued:'分级中', scored:'已分级'};
export const HANDOVERS = {open:'待签收', signed:'已签收', superseded:'已作废'};
export const SHIFTS = {day:'早班', swing:'中班', night:'晚班'};
export const PRIORITIES = {1:'常规跟进', 2:'尽快跟进', 3:'优先处理'};
export const FEATURES = {missed_round:'计划巡房未完成', repeated_call:'一小时内重复呼叫', transfer_support:'请求协助移位', unfinished_task:'照护任务尚未完成'};

export function escape(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
export function time(value) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('zh-CN', {month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',
    hourCycle:'h23',timeZone:'Asia/Shanghai'}).format(new Date(value));
}
export function pill(label, tone='neutral') { return `<span class="pill ${tone}">${escape(label)}</span>`; }
export function priority(level) { return level ? pill(PRIORITIES[level], `level-${level}`) : pill('未分级'); }
export function status(value, labels=ALERTS) {
  const tone = ['incomplete','superseded'].includes(value) ? 'warn' : ['confirmed','signed','closed','scored'].includes(value) ? 'good' : 'neutral';
  return pill(labels[value] || value, tone);
}
export function empty(message) { return `<div class="empty">${escape(message)}</div>`; }
export function button(label, classes='primary') { return `<button type="submit" class="${classes}">${escape(label)}</button>`; }
export function brand() { return '<div class="brand"><span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i><i></i></span><div><strong>朝晖照护</strong><small>值班工作台</small></div></div>'; }
export function heading(label, title, description, right='') {
  return `<header class="page-heading"><div><p class="overline">${escape(label)}</p><h1>${escape(title)}</h1><p>${escape(description)}</p></div>${right}</header>`;
}
export function panel(title, note='') { return `<div class="panel-title"><h2>${escape(title)}</h2>${note ? `<p>${escape(note)}</p>` : ''}</div>`; }
export function signalInputs(row={}) {
  return Object.entries(FEATURES).map(([key, label]) => `<fieldset class="signal"><legend>${label}</legend>${row[key] === true || row[key] === false ?
    `<span class="locked">已记录 · ${row[key] ? '是' : '否'}</span>` : `<div class="choices">
    <label><input type="radio" name="${key}" value="true"><span>是</span></label>
    <label><input type="radio" name="${key}" value="false"><span>否</span></label>
    <label><input type="radio" name="${key}" value="" checked><span>待确认</span></label></div>`}</fieldset>`).join('');
}
export function signalValues(form) {
  return Object.fromEntries(Object.keys(FEATURES).filter(key => form.get(key)).map(key => [key, form.get(key) === 'true']));
}
