import {roleOptions} from './coverageDispatch.js';
import {api} from './store.js';
import {button, empty, escape, heading, panel, pill, SHIFTS, time} from './shared.js';

const coverageStates = {active:'覆盖中', expired:'窗口已到期', ended:'已结束'};

function coverageCard(row, lead) {
  const end = lead && row.status !== 'ended' ? `<details class="ops-actions"><summary>登记结束</summary>
    <form class="stack ops-action" data-do="endCoverage" data-id="${row.id}">
    <label>结束说明<textarea name="reason" rows="2" minlength="3" maxlength="600" required></textarea></label>${button('结束覆盖','secondary')}</form></details>` : '';
  return `<article class="ops-item"><div class="ops-item-head"><div><h3>${escape(row.unit)} · ${SHIFTS[row.shift]}</h3>
    <p>${escape(row.carer_name)} · ${time(row.started_at)} 至 ${time(row.ends_at)}</p></div>
    <div class="data-line">${pill(coverageStates[row.status],row.status === 'active' ? 'good' : 'neutral')}${pill(`在办 ${row.active_count} / 容量 ${row.capacity}`,row.active_count >= row.capacity ? 'warn' : 'neutral')}</div></div>
    ${row.end_reason ? `<p class="ops-copy">${time(row.ended_at)} · ${escape(row.end_reason)}</p>` : ''}${end}</article>`;
}

function rosterForm(units, carers) {
  return `<section class="paper ops-create">${panel('登记覆盖','登记后，该区域的响应按当班时限与容量派发。')}
    <form class="stack ops-action" data-do="startCoverage">
      <label>照护区域<select name="unit" required>${roleOptions(units.map(unit=>[unit,unit]))}</select></label>
      <label>照护员<select name="carer_id" required>${roleOptions(carers.map(row=>[row.id,row.name]))}</select></label>
      <div class="paired-fields"><label>班次<select name="shift">${roleOptions(Object.entries(SHIFTS))}</select></label>
      <label>覆盖时长<select name="duration_minutes">${roleOptions([[480,'8 小时'],[240,'4 小时'],[120,'2 小时'],[60,'1 小时']])}</select></label></div>
      <label>同时在办上限<input title="1 到 5 条" name="capacity" type="number" min="1" max="5" value="2" required></label>
      ${button('开始覆盖')}</form></section>`;
}

export async function shiftCoveragePage(state) {
  const {items,units,carers} = await api('/shift-coverage');
  const lead = state.user.role === 'lead';
  const active = items.filter(row=>row.status === 'active');
  const history = items.filter(row=>row.status !== 'active');
  return `${heading('照护响应','值班覆盖','查看各照护区域的值班时限与响应容量。','<a class="secondary" href="#alerts">返回告警队列</a>')}
    <div class="ops-layout"><div class="stack">
      <section class="paper">${panel('当前覆盖',`${active.length} 条 · ${new Set(active.map(row=>row.unit)).size} 个区域`)}
      ${active.map(row=>coverageCard(row,lead)).join('') || empty('暂无生效的值班覆盖。')}</section>
      ${history.length ? `<section class="paper">${panel('覆盖记录')}${history.map(row=>coverageCard(row,lead)).join('')}</section>` : ''}
    </div>${lead && units.length && carers.length ? rosterForm(units,carers) : ''}</div>`;
}

export const coverageActions = {
  async startCoverage(_form,data) {
    const payload = Object.fromEntries(data);
    for (const field of ['carer_id','duration_minutes','capacity']) payload[field] = Number(payload[field]);
    await api('/shift-coverage','POST',payload);
    return '值班覆盖已开始';
  },
  async endCoverage(form,data) {
    await api(`/shift-coverage/${form.dataset.id}/end`,'POST',Object.fromEntries(data));
    return '值班覆盖已结束';
  },
};
