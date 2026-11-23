import {button, escape, pill, time} from './shared.js';

const kinds = {room_round:'现场巡房', call_log:'呼叫记录', transfer_assistance:'协助移位安排', task_receipt:'任务回执', handover_note:'交班补记'};
const states = {pending:'待核对', verified:'已核对', blocked:'受阻', retry:'安排复核'};

export function planForm(responseId) {
  return `<form class="stack ops-action" data-do="planChecks" data-id="${responseId}">
    <p class="field-hint">填写本次需要核对的项目，留空的项目会跳过。</p>
    ${Object.entries(kinds).map(([key,label])=>`<label>${label}<textarea name="${key}" rows="2" minlength="3" maxlength="600"></textarea></label>`).join('')}
    ${button('保存核对清单')}</form>`;
}

export function checkItem(row, canVerify, canRetry) {
  const ownForm = canVerify && row.status === 'pending' ? `<form class="stack" data-do="recordCheck" data-id="${row.id}" data-version="${row.version}">
    <div class="paired-fields"><label>本次结论<select name="outcome"><option value="verified">已核对</option><option value="blocked">受阻</option></select></label>
    <label>核对凭据或阻碍<textarea name="note" rows="2" minlength="3" maxlength="600" required></textarea></label></div>${button('登记核对结果')}</form>` : '';
  const retryForm = canRetry && row.status === 'blocked' ? `<form class="stack" data-do="retryCheck" data-id="${row.id}" data-version="${row.version}">
    <label>复核安排<textarea name="note" rows="2" minlength="3" maxlength="600" required></textarea></label>${button('重新安排核对','secondary')}</form>` : '';
  const history = row.history.length ? `<ol class="check-history">${row.history.map(entry=>`<li><div class="data-line"><strong>${states[entry.action]}</strong>
    <span>${escape(entry.actor)} · ${time(entry.recorded_at)}</span></div><p>${escape(entry.note)}</p></li>`).join('')}</ol>` : '';
  return `<article class="ops-item check-item"><div class="ops-item-head"><div><h3>${kinds[row.kind]}</h3><p>${escape(row.instruction)}</p></div>
    ${pill(states[row.status],row.status === 'verified' ? 'good' : row.status === 'blocked' ? 'warn' : 'neutral')}</div>${history}${ownForm}${retryForm}</article>`;
}
