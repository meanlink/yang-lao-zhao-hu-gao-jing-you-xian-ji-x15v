import {checkItem, planForm} from './checklistItems.js';
import {api} from './store.js';
import {empty, escape, heading, panel, pill, time} from './shared.js';

async function checklistQueue() {
  const {items} = await api('/care-responses');
  const relevant = items.filter(row=>row.coverage_id || row.check_count);
  return `${heading('照护响应','处置核对','打开响应对应的核对清单，查看凭据和受阻项目。',
    '<a class="secondary" href="#responses">查看响应</a>')}
    <section class="paper">${panel('响应清单',`${relevant.length} 条响应`)}${relevant.map(row=>`<article class="ops-item"><div class="ops-item-head">
      <div><h3><a class="text-link" href="#checks/${row.id}">${escape(row.room)} · ${escape(row.resident_name)}</a></h3>
      <p>响应 #${row.id} · ${escape(row.assignee)} · 截止 ${time(row.due_at)}</p></div>
      <div class="data-line">${checkProgress(row)}</div></div></article>`).join('') || empty('暂无需要结构化核对的响应。')}</section>`;
}

export function checkProgress(row) {
  if (!row.check_count) return row.coverage_id ? pill('待制定清单','warn') : '';
  return `${pill(`已核对 ${row.verified_count} / ${row.check_count}`,row.verified_count === row.check_count ? 'good' : 'neutral')}${row.blocked_count ? pill(`受阻 ${row.blocked_count} 项`,'warn') : ''}`;
}

export async function responseChecksPage(state,responseId) {
  if (!responseId) return checklistQueue();
  const {response,items} = await api(`/care-responses/${responseId}/checks`);
  const accepted = response.status === 'accepted';
  const active = accepted || response.status === 'assigned';
  const lead = state.user.role === 'lead';
  const own = state.user.role === 'carer' && state.user.id === response.assigned_to;
  const verified = items.filter(item=>item.status === 'verified').length;
  const blocked = items.filter(item=>item.status === 'blocked').length;
  const plan = lead && active && !items.length ? planForm(response.id) : '';
  return `${heading('处置核对',`${response.room} · ${response.resident_name}`,`${response.unit} · 响应 #${response.id} · ${response.assignee}`,
    `<a class="secondary" href="#responses/${response.alert_id}">返回响应</a>`)}
    <div class="check-summary paper"><div><strong>${items.length ? `${verified} / ${items.length} 项已核对` : '待制定核对清单'}</strong>
    <p>${response.planned_at ? `${escape(response.planner)} · ${time(response.planned_at)} 制定` : escape(response.instruction)}</p></div>
    <div class="data-line">${blocked ? pill(`${blocked} 项受阻`,'warn') : ''}${pill(`处置截止 ${time(response.due_at)}`)}</div></div>
    <section class="paper check-workspace">${panel('核对项目')}${items.map(item=>checkItem(item,accepted && own,accepted && lead)).join('') || plan || empty('值班长尚未登记此响应的核对项目。')}</section>`;
}

async function record(form,data,operation) {
  const body = {...Object.fromEntries(data), version:Number(form.dataset.version)};
  await api(`/response-check-items/${form.dataset.id}/${operation}`,'POST',body);
}

export const checkActions = {
  async planChecks(form,data) {
    const items = [...data].filter(([,value])=>value.trim()).map(([kind,instruction])=>({kind,instruction}));
    if (!items.length) throw new Error('请至少填写一项核对要求');
    await api(`/care-responses/${form.dataset.id}/checks`,'POST',{items});
    return '核对清单已保存';
  },
  async recordCheck(form,data) { await record(form,data,'result'); return '核对结果已登记'; },
  async retryCheck(form,data) { await record(form,data,'retry'); return '已重新安排核对'; },
};
