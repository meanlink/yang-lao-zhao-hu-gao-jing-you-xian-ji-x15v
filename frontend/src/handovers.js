import {api} from './store.js';
import {HANDOVERS, SHIFTS, button, empty, escape, heading, panel, priority, status, time} from './shared.js';

export async function handoversPage(state) {
  const rows = await api('/handovers');
  const open = rows.filter(row => row.status === 'open');
  const archive = rows.filter(row => row.status !== 'open');
  const entry = (r, signable) => `<article class="handover-entry"><div class="handover-meta"><span>交班 #${r.id} · ${SHIFTS[r.target_shift]}</span>${status(r.status,HANDOVERS)}</div>
    <h3>${escape(r.snapshot.resident.room)} · ${escape(r.snapshot.resident.name)}</h3><div class="data-line">${priority(r.snapshot.priority)} <span>${escape(r.created_name)} · ${time(r.created_at)}</span></div>
    <dl><dt>接续事项</dt><dd>${escape(r.next_action)}</dd><dt>复核说明</dt><dd>${escape(r.snapshot.review_note)}</dd></dl>
    ${(r.snapshot.response_checks || []).map(check=>`<div class="note good"><strong>处置核对 · ${escape(check.assignee)} · ${check.verified_count} 项已核对</strong>
    <p>${escape(check.finish_note)}</p><a class="text-link" href="#checks/${check.response_id}">查看核对凭据</a></div>`).join('')}
    <details><summary>关联观察与告警版本</summary><p>告警 #${r.alert_id} · 版本 ${r.alert_revision}</p><ul>${r.snapshot.observations.map(obs=>`<li>${escape(obs.ref)}</li>`).join('')}</ul></details>
    ${r.status==='signed' ? `<div class="note good"><strong>${escape(r.signed_name)} · ${time(r.signed_at)}</strong><p>${escape(r.receipt_note)}</p><a class="text-link" href="#followups/${r.id}">查看或安排交班后复查</a></div>` : ''}
    ${signable ? `<form data-do="sign" data-id="${r.id}" class="stack sign-form"><label>签收说明<input name="receipt_note" minlength="3" maxlength="600" required placeholder="说明已接续事项和下一步"></label>${button('确认签收')}</form>` : ''}</article>`;
  return `${heading('交班记录','本班交接清单','交班单保留当时的复核版本与观察，接班员签收后完成本轮交接。')}
    <div class="split handover-split"><section class="paper">${panel('待签收', `${open.length} 份交班单`)}${open.length ? open.map(r=>entry(r,state.user.role==='receiver')).join('') : empty('当前无待签交班。值班长复核告警后可提交。')}</section>
    <section class="paper">${panel('交班归档', `${archive.length} 份历史交班单`)}${archive.length ? archive.map(r=>entry(r,false)).join('') : empty('签收或因新增观察作废的交班单会显示在这里。')}</section></div>`;
}
