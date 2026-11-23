import {api} from './store.js';
import {ALERTS, button, empty, escape, heading, panel, priority, status} from './shared.js';

export async function residentsPage(state) {
  const rows = await api('/residents');
  const units = [...new Set(rows.map(row => row.unit))];
  const filtered = rows.filter(row => !state.unit || row.unit === state.unit);
  const register = state.user.role === 'lead' ? `<details class="side-paper"><summary>登记住户</summary>
    <form data-do="register" class="stack">
      <label>住户编号<input name="code" required pattern="ZH-[0-9]{3}" placeholder="ZH-305"></label>
      <label>姓名<input name="name" required maxlength="100"></label>
      <label>床位<input name="room" required maxlength="100" placeholder="305-A"></label>
      <label>翼区及楼层<input name="unit" required maxlength="100" placeholder="西翼三层"></label>
      <label>交班照护要点<textarea name="care_plan" required minlength="3" maxlength="600"></textarea></label>
      ${button('保存档案')}
    </form></details>` : '';
  return `${heading('住户档案','按楼层查看住户','核对床位和照护要点，再进入观察记录。')}
    <div class="unit-filter" aria-label="按翼区筛选">${['', ...units].map(unit => `<button type="button" data-action="unit" data-value="${escape(unit)}" class="${unit===state.unit ? 'selected' : ''}">${escape(unit || '全部翼区')} <span>${rows.filter(x => !unit || unit === x.unit).length}</span></button>`).join('')}</div>
    <div class="split directory"><section class="paper">${panel('床位与照护要点', `${filtered.length} 位住户`)}
      ${filtered.length ? filtered.map(r => `<article class="resident-row"><div class="room-stamp">${escape(r.room)}</div><div>
        <p class="eyebrow">${escape(r.unit)} · ${escape(r.code)}</p><h3>${escape(r.name)}</h3><p>${escape(r.care_plan)}</p>
        <div class="data-line">${r.alert_id ? `${priority(r.priority)} ${status(r.alert_status, ALERTS)}` : '<span>当前无在办告警</span>'}<span>${r.observation_count} 条观察</span></div></div>
        <button type="button" class="text-link" data-action="resident-observations" data-value="${r.id}">照护观察 <span aria-hidden="true">↗</span></button></article>`).join('') : empty('当前翼区没有住户。')}
      </section><aside>${register}<div class="side-paper"><h3>登记口径</h3><p>住户编号按入住档案录入。记录跨班需持续确认的照护要点。</p></div></aside></div>`;
}
