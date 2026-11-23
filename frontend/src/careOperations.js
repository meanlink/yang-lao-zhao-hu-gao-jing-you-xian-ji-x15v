import {api} from './store.js';
import {dispatchForm, dispatchPayload} from './coverageDispatch.js';
import {checkProgress} from './responseChecks.js';
import {button, empty, escape, heading, panel, pill, priority, SHIFTS, time} from './shared.js';

const responses = {assigned:'待接单', accepted:'处置中', completed:'已处置', cancelled:'已撤销'};
const contacts = {open:'首次联络', callback:'待回拨', reached:'已联络'};
const contactRoles = {primary:'第一联系人', backup:'备用联系人'};
const channels = {phone:'电话', in_person:'当面'};
const outcomes = {no_answer:'未接通', requested_callback:'约定回拨', reached:'已确认接通'};
const followups = {scheduled:'待复查', stable:'复查正常', referred:'已转照护观察'};
const liveResponse = row => ['assigned', 'accepted'].includes(row.status);
const alertLink = id => `<a class="text-link" href="#alerts/${id}">告警 #${id}</a>`;
const query = (field, id) => id ? `?${field}=${id}` : '';

function options(values) {
  return Object.entries(values).map(([id,label]) => `<option value="${escape(id)}">${escape(label)}</option>`).join('');
}

function noteField(label, name, placeholder) {
  return `<label>${escape(label)}<textarea name="${name}" rows="2" minlength="3" maxlength="600" required placeholder="${escape(placeholder)}"></textarea></label>`;
}

function createPanel(title, subtitle, form) {
  return `<section class="paper ops-create">${panel(title, subtitle)}${form}</section>`;
}

function item(row, badge, intro, detail, actions='') {
  return `<article class="ops-item"><div class="ops-item-head"><div><h3>${escape(row.room)} · ${escape(row.resident_name)}</h3>
    <p>${intro}</p></div><div class="data-line">${badge}</div></div>${detail}${actions}</article>`;
}

function workspace({section, title, description, source, sourceLabel, back, rows, label, side, fallback}) {
  return `${heading(section,title,description,back)}${source ? `<div class="ops-source">${source}</div>` : ''}
    <div class="ops-layout"><section class="paper">${panel(label, sourceLabel)}${rows || empty(fallback)}</section>${side || ''}</div>`;
}

export async function responsesPage(state, alertId) {
  const [{items,carers}, alert, coverage] = await Promise.all([
    api(`/care-responses${query('alert_id',alertId)}`),
    alertId ? api(`/alerts/${alertId}`) : null,
    alertId && state.user.role === 'lead' ? api(`/alerts/${alertId}/coverage`) : null,
  ]);
  const countActive = items.filter(liveResponse).length;
  const rows = items.map(row => {
    const own = state.user.role === 'carer' && state.user.id === row.assigned_to;
    const accept = own && row.status === 'assigned' ? `<form data-do="acceptResponse" data-id="${row.id}">${button('接单')}</form>` : '';
    const checksReady = row.check_count ? row.verified_count === row.check_count : !row.coverage_id;
    const checksLink = row.coverage_id || row.check_count || (liveResponse(row) && state.user.role === 'lead')
      ? `<div class="data-line"><a class="text-link" href="#checks/${row.id}">处置核对清单</a>${checkProgress(row)}</div>` : '';
    const complete = own && row.status === 'accepted' && checksReady ? `<form class="stack ops-action" data-do="completeResponse" data-id="${row.id}">
      ${noteField('处置结果','note','记录已完成的核对和处置')}${button('提交处置结果')}</form>` : '';
    const cancel = liveResponse(row) && state.user.role === 'lead' ? `<details class="ops-actions"><summary>撤销任务</summary>
      <form class="stack ops-action" data-do="cancelResponse" data-id="${row.id}">${noteField('撤销原因','note','说明重复派单或接单人变更')}${button('确认撤销','secondary')}</form></details>` : '';
    const badge = `${pill(responses[row.status], row.status === 'completed' ? 'good' : 'neutral')}${row.overdue ? pill('已超时','warn') : ''}`;
    return item(row,badge,`${alertLink(row.alert_id)} · 版本 ${row.alert_revision} · 任务 #${row.id}`,
      `<div class="data-line">${priority(row.priority)} <span>${escape(row.assignee)}${row.assigned_shift ? ` · ${SHIFTS[row.assigned_shift]}` : ''} · 截止 ${time(row.due_at)}</span></div>
      <p class="ops-copy">${escape(row.instruction)}</p>${row.finish_note ? `<div class="note"><strong>${row.status === 'cancelled' ? '撤销说明' : '处置回执'}</strong><p>${escape(row.finish_note)}</p></div>` : ''}`,
      `${checksLink}${accept}${complete}${cancel}`);
  }).join('');
  const canAssign = alert?.status === 'confirmed' && !alert.active_response_id && state.user.role === 'lead';
  const side = canAssign ? createPanel('派发响应','时限按告警的已复核优先级生成。',
    dispatchForm(alert,coverage,carers,noteField('处置要求','instruction','例如核对床头呼叫记录与巡房回执'))) : '';
  return workspace({section:'照护响应', title:'照护响应派单', description:'值班长派发已复核告警，照护员接单并提交处置回执。',
    source:alert && `${escape(alert.room)} · ${escape(alert.resident_name)} · ${alertLink(alert.id)}`,
    sourceLabel:`${countActive} 条在办 · ${items.filter(row=>row.overdue).length} 条超时`,
    back:`<a class="secondary" href="${alert ? '#responses' : '#alerts'}">${alert ? '查看全部响应' : '从告警选择'}</a>`,
    rows, label:'响应清单', side, fallback:'暂无响应记录。值班长可以从已复核告警发起派单。'});
}

export async function contactsPage(state, alertId) {
  const [items, alert] = await Promise.all([api(`/family-contacts${query('alert_id',alertId)}`), alertId ? api(`/alerts/${alertId}`) : null]);
  const rows = items.map(row => {
    const timeline = row.attempts.map(attempt => `<li><strong>${outcomes[attempt.outcome]}</strong><small>${channels[attempt.channel]} · ${escape(attempt.recorder)} · ${time(attempt.attempted_at)}</small><p>${escape(attempt.note)}</p></li>`).join('');
    const form = ['carer','lead'].includes(state.user.role) && row.status !== 'reached' ? `<form class="stack ops-action" data-do="recordAttempt" data-id="${row.id}" data-attempt="${row.attempts[0]?.id || 0}">
      <div class="ops-fields"><label>联络方式<select name="channel">${options(channels)}</select></label>
      <label>联系结果<select name="outcome">${options(outcomes)}</select></label></div>
      ${noteField('联络纪要','note','记录沟通结果及下一步')}${button('登记联系结果')}</form>` : '';
    return item(row,pill(contacts[row.status],row.status === 'reached' ? 'good' : row.due ? 'warn' : 'neutral'),
      `${alertLink(row.alert_id)} · ${contactRoles[row.contact_role]}`,
      `<p class="ops-copy">${escape(row.purpose)}</p>${row.next_contact_at ? `<p class="ops-time">${row.status === 'open' ? '首次联络' : '回拨时间'} ${time(row.next_contact_at)}</p>` : ''}
       ${timeline ? `<ol class="ops-timeline" aria-label="联络轨迹">${timeline}</ol>` : ''}`,form);
  }).join('');
  const canOpen = alert && ['confirmed','handover','closed'].includes(alert.status) && state.user.role === 'lead' && !items.length;
  const side = canOpen ? createPanel('登记联络事项','选择联系人，填写本次联络目的。',
    `<form data-do="openContact" data-id="${alert.id}" class="stack ops-action"><label>联系对象<select name="contact_role">${options(contactRoles)}</select></label>
      ${noteField('联络目的','purpose','例如确认家属是否能来中心核对本班记录')}${button('建立联络事项')}</form>`) : '';
  return workspace({section:'家属联络', title:'家属联络留痕', description:'记录每次联系结果，按回拨时间跟进。',
    source:alert && `${escape(alert.room)} · ${escape(alert.resident_name)} · ${alertLink(alert.id)}`,
    sourceLabel:`${items.filter(row=>row.due).length} 项到期 · ${items.filter(row=>row.status==='reached').length} 项已联络`,
    back:`<a class="secondary" href="${alert ? '#contacts' : '#alerts'}">${alert ? '查看全部联络' : '从告警选择'}</a>`,
    rows, label:'联系台账', side, fallback:'暂无联络事项。值班长可从已复核的告警登记。'});
}

export async function followupsPage(state, handoverId) {
  const [items, handovers] = await Promise.all([
    api(`/handover-followups${query('handover_id',handoverId)}`), handoverId ? api('/handovers') : [],
  ]);
  const handover = handovers.find(row => row.id === handoverId);
  const rows = items.map(row => {
    const form = row.status === 'scheduled' && state.user.role === 'receiver' ? `<form class="stack ops-action" data-do="finishFollowup" data-id="${row.id}">
      <label>复查结论<select name="result" required><option value="stable">接续事项已核对</option><option value="needs_attention">发现异常，转照护观察</option></select></label>
      ${noteField('现场记录','note','记录现场事实与待核对内容')}${button('提交复查结论')}</form>` : '';
    const referral = row.referred_alert_id ? `<p class="ops-time">待补观察 ${escape(row.observation_ref)} · ${alertLink(row.referred_alert_id)}</p>` : '';
    return item(row,`${pill(followups[row.status],row.status === 'stable' ? 'good' : 'neutral')}${row.overdue ? pill('已逾期','warn') : ''}`,
      `交班 #${row.handover_id} · ${SHIFTS[row.target_shift]} · ${alertLink(row.alert_id)}`,
      `<p class="ops-time">复查截止 ${time(row.due_at)}</p><p class="ops-copy">${escape(row.checklist)}</p>
       ${row.result_note ? `<div class="note"><strong>现场记录</strong><p>${escape(row.result_note)}</p>${referral}</div>` : ''}`,form);
  }).join('');
  const side = handover?.status === 'signed' && !items.length && state.user.role === 'receiver' ? createPanel('安排复查','以签收的接续事项为依据记录核对计划。',
    `<form data-do="scheduleFollowup" data-id="${handover.id}" class="stack ops-action">
      <label>完成时限<select name="delay_minutes">${options({15:'15 分钟',30:'30 分钟',60:'60 分钟',120:'120 分钟'})}</select></label>
      ${noteField('复查内容','checklist','例如核对巡视回执并记录住户当前情况')}${button('加入复查清单')}</form>`) : '';
  const source = handover && `${escape(handover.snapshot.resident.room)} · ${escape(handover.snapshot.resident.name)} · 交班 #${handover.id}<p class="ops-copy">${escape(handover.next_action)}</p>`;
  return workspace({section:'接班工作', title:'交班后复查', description:'接班员登记复查计划，发现异常时补回照护观察队列。',
    source, sourceLabel:`${items.filter(row=>row.status==='scheduled').length} 项待查 · ${items.filter(row=>row.overdue).length} 项逾期`,
    back:`<a class="secondary" href="${handover ? '#followups' : '#handovers'}">${handover ? '查看全部复查' : '从交班选择'}</a>`,
    rows, label:'复查清单', side, fallback:'暂无复查记录。接班员可从已签收的交班单安排。'});
}

function write(path, body, message) {
  return api(path, 'POST', body).then(() => message);
}

export const careOperationsActions = {
  assignResponse(form,data) {
    return write(`/alerts/${form.dataset.id}/care-responses`, dispatchPayload(form,data), '响应任务已派发');
  },
  acceptResponse(form) { return write(`/care-responses/${form.dataset.id}/accept`, {}, '已接单'); },
  completeResponse(form,data) { return write(`/care-responses/${form.dataset.id}/complete`, Object.fromEntries(data), '处置回执已提交'); },
  cancelResponse(form,data) { return write(`/care-responses/${form.dataset.id}/cancel`, Object.fromEntries(data), '响应任务已撤销'); },
  openContact(form,data) { return write(`/alerts/${form.dataset.id}/family-contact`, Object.fromEntries(data), '联络事项已登记'); },
  recordAttempt(form,data) {
    return write(`/family-contacts/${form.dataset.id}/attempts`, {...Object.fromEntries(data),expected_attempt_id:Number(form.dataset.attempt)}, '联系结果已留档');
  },
  scheduleFollowup(form,data) {
    return write(`/handovers/${form.dataset.id}/followup`, {checklist:data.get('checklist'),delay_minutes:Number(data.get('delay_minutes'))}, '复查计划已登记');
  },
  finishFollowup(form,data) { return write(`/handover-followups/${form.dataset.id}/complete`, Object.fromEntries(data), '复查结论已提交'); },
};
