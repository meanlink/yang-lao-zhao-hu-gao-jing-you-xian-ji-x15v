import {button, escape, pill, SHIFTS, time} from './shared.js';

export function roleOptions(rows) {
  return rows.map(([value, label]) => `<option value="${escape(value)}">${escape(label)}</option>`).join('');
}

export function eligibility(row) {
  if (row.status !== 'active') return ['已结束', 'neutral'];
  if (!row.covers_deadline) return ['覆盖时限不足', 'warn'];
  if (row.active_count >= row.capacity) return ['响应容量已满', 'warn'];
  return ['可派发', 'good'];
}

export function dispatchForm(alert, coverage, carers, instructionField) {
  const managed = coverage.managed;
  const choices = managed ? coverage.items.filter(row => eligibility(row)[1] === 'good') : carers;
  const preview = managed ? `<div class="coverage-dispatch-meta"><p>${escape(coverage.unit)} · 需覆盖 ${coverage.sla_minutes} 分钟</p>
    ${coverage.items.filter(row => row.status === 'active').map(row => `<div class="data-line"><span>${escape(row.carer_name)} · ${row.active_count}/${row.capacity}</span>${pill(...eligibility(row))}</div>`).join('')}
    <a class="text-link" href="#coverage">查看值班覆盖</a></div>` : '';
  if (!choices.length) {
    return `${preview}<div class="note warn dispatch-empty">${managed ? '当前没有能覆盖本任务时限且有空余容量的照护员。' : '暂无可用照护员。'}</div>`;
  }
  const options = choices.map(row => [managed ? `${row.carer_id}:${row.id}` : row.id,
    managed ? `${row.carer_name} · ${SHIFTS[row.shift]} · 至 ${time(row.ends_at)}` : row.name]);
  return `${preview}<form data-do="assignResponse" data-id="${alert.id}" data-revision="${alert.revision}" class="stack ops-action">
    <label>接单照护员<select name="assigned_to" required>${roleOptions(options)}</select></label>
    ${instructionField}${button('派发给照护员')}</form>`;
}

export function dispatchPayload(form, data) {
  const [assignee, coverage] = data.get('assigned_to').split(':');
  const payload = {revision:Number(form.dataset.revision), assigned_to:Number(assignee), instruction:data.get('instruction')};
  if (coverage) payload.coverage_id = Number(coverage);
  return payload;
}
