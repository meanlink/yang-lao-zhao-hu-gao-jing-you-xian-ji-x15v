import {api} from './store.js';
import {OBSERVATIONS, FEATURES, button, empty, escape, heading, panel, signalInputs, status, time} from './shared.js';

export async function observationsPage(state) {
  const query = state.observationResident ? `?resident_id=${state.observationResident}` : '';
  const [residents, rows] = await Promise.all([api('/residents'), api(`/observations${query}`)]);
  const selected = rows.find(row => row.id === state.supplement && row.status === 'incomplete');
  const options = residents.map(r => `<option value="${r.id}" ${String(r.id) === state.observationResident ? 'selected' : ''}>${escape(r.room)} · ${escape(r.name)}</option>`).join('');
  const canWrite = state.user.role !== 'receiver';
  const editor = !canWrite ? `<div class="side-paper"><h3>接班员视角</h3><p>可查看观察记录和告警，交班签收在交班记录页完成。</p></div>` : selected ? `
    <section class="paper">${panel('补齐关键观察', selected.ref)}<form data-do="supplement" data-id="${selected.id}" class="stack form-pad">
      <div class="note warn">待补字段确认后再填写。已登记的字段会保留。</div>
      ${signalInputs(selected)}<div class="actions">${button('保存补录')}<button type="button" data-action="cancel-supplement" class="secondary">取消</button></div>
    </form></section>` : `<section class="paper">${panel('录入新观察','带上巡房单或值班本的记录编号。')}
    <form data-do="observe" class="stack form-pad"><div class="form-pair"><label>住户<select name="resident_id" required>
      <option value="">选择床位</option>${options}</select></label><label>观察编号<input name="ref" required pattern="[A-Z0-9][A-Z0-9\\-]{4,39}" placeholder="OBS-20261121-01"></label></div>
      ${signalInputs()}<label>观察摘要<textarea name="author_note" minlength="3" maxlength="600" required placeholder="记录本班看到的情况和需要核对的事项"></textarea></label>
      ${button('保存观察')}</form></section>`;
  return `${heading('照护观察','巡视与任务观察','逐项确认信号。待确认的记录会进入待补队列。')}
    <div class="split"><section class="paper">${panel('观察流水','按录入时间倒序')}
    <div class="filter-row"><label>按住户筛选 <select data-change="observation-resident"><option value="">全部住户</option>${options}</select></label>
      <button class="text-link" data-action="refresh" type="button">刷新</button></div>
    ${rows.length ? rows.map(r => `<article class="journal-entry"><div class="data-line">${status(r.status, OBSERVATIONS)}<span>${escape(r.ref)} · ${time(r.observed_at)}</span></div>
    <h3>${escape(r.room)} · ${escape(r.resident_name)}</h3><p>${escape(r.author_note)}</p>
    ${r.status === 'incomplete' ? `<p class="missing">待核对 ${Object.entries(FEATURES).filter(([key])=>r[key]===null).map(([,label])=>label).join('、')}</p>` : ''}
    <div class="data-line"><span>记录人 ${escape(r.author_name)}</span>${canWrite && r.status==='incomplete' ? `<button type="button" class="text-link" data-action="supplement" data-value="${r.id}">补录</button>` : ''}<a href="#alerts/${r.alert_id}">查看告警</a></div></article>`).join('') : empty('暂无观察。可选择其他住户或录入新观察。')}
    </section>${editor}</div>`;
}
