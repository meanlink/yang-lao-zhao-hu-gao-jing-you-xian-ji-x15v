import {api} from './store.js';
import {MODEL_VERSIONS, PRIORITIES, TRIAL_RUNS, button, empty, escape, heading, panel, pill, priority, status, time} from './shared.js';

function versionEntry(v, isLead) {
  const rows = v.description?.training_rows ? `${v.description.training_rows} 行样本` : '样本行数未知';
  const ops = !isLead || v.status !== 'draft' ? '' : `<div class="ops-links">
    <form data-do="create-trial" data-id="${v.id}" class="stack"><input name="note" maxlength="600" placeholder="试算备注（可选）"><button type="submit" class="secondary">创建试算</button></form>
    <form data-do="activate-version" data-id="${v.id}">${button('启用新版')}</form></div>`;
  return `<article class="journal-entry"><div class="data-line">${status(v.status, MODEL_VERSIONS)}<span>${escape(v.label)}</span></div>
    <div class="data-line"><span>校验 ${escape(v.checksum.slice(0,12))} · ${rows}</span><span>${v.observation_count} 条观察使用</span></div>
    <div class="data-line"><span>登记 ${v.registered_name ? escape(v.registered_name) + ' · ' : ''}${time(v.created_at)}</span>${v.activated_at ? `<span>启用 ${time(v.activated_at)}</span>` : ''}</div>
    ${ops}</article>`;
}

function trialRunRow(run, expanded) {
  return `<article class="journal-entry"><div class="data-line">${status(run.status, TRIAL_RUNS)}<span>批次 #${run.id} · ${escape(run.version_label)}</span></div>
    <div class="data-line"><span>进度 ${run.done}/${run.total}</span><span>${pill(`差异 ${run.changed}`, run.changed ? 'warn' : 'neutral')}</span></div>
    <div class="data-line"><span>${escape(run.created_name)} · ${time(run.created_at)}</span>
      <button type="button" class="text-link" data-action="${expanded ? 'close-trial' : 'trial-detail'}" data-value="${run.id}">${expanded ? '收起' : '查看差异'}</button></div>
    ${run.note ? `<p>${escape(run.note)}</p>` : ''}</article>`;
}

function trialDetail(run) {
  const rows = run.items.map(item => {
    const before = item.baseline?.candidate;
    const after = item.trial?.candidate;
    const verdict = item.status === 'done'
      ? (item.changed ? pill('等级变化', 'warn') : pill('一致', 'good'))
      : pill('待算');
    return `<div class="data-line"><span>${escape(item.ref)} · ${escape(item.room)} ${escape(item.resident_name)}</span><span>${before ? PRIORITIES[before] : '—'} → ${after ? PRIORITIES[after] : '待算'} ${verdict}</span></div>`;
  }).join('');
  return `<section class="paper">${panel(`批次 #${run.id} 差异明细`, `${escape(run.version_label)} · 试算前后等级对比`)}
    <div class="detail-pad">${run.items.length ? rows : empty('该批次没有试算条目。')}</div></section>`;
}

export async function modelVersionsPage(state) {
  const isLead = state.user.role === 'lead';
  const [versions, runs] = await Promise.all([api('/model-versions'), api('/trial-runs')]);
  const expanded = state.trialRun && runs.some(r => r.id === state.trialRun) ? await api(`/trial-runs/${state.trialRun}`) : null;
  const active = versions.find(v => v.status === 'active');
  const register = !isLead ? '' : `<section class="paper">${panel('登记新版样本','粘贴新的分级语料，保存为待启用版本。')}
    <form data-do="register-version" class="stack form-pad">
      <label>版本名称<input name="label" maxlength="100" required placeholder="例如 2026-12 修订样本"></label>
      <label>分级语料（CSV）<textarea name="corpus" rows="8" required placeholder="priority,missed_round,repeated_call,transfer_support,unfinished_task"></textarea></label>
      <div class="note">语料需含三类等级，四项信号取 0 或 1。登记后先创建试算比对差异，再决定是否启用。</div>
      ${button('保存为待启用版本')}</form></section>`;
  return `${heading('分级版本','样本版本与试算','新版样本先对一批已评分观察试算，核对差异后再启用。')}
    <div class="briefing"><div><strong>${active ? escape(active.label) : '—'}</strong><span>使用中版本</span></div>
      <div><strong>${versions.filter(v => v.status === 'draft').length}</strong><span>待启用版本</span></div>
      <div><strong>${runs.filter(r => r.status === 'running').length}</strong><span>试算中批次</span></div></div>
    <div class="split"><section class="paper">${panel('版本清单','新登记的观察按使用中版本分级；已排队和待补的观察仍按登记时版本。')}
      ${versions.length ? versions.map(v => versionEntry(v, isLead)).join('') : empty('暂无分级版本。')}</section>
      <div class="stack">${register}
      <section class="paper">${panel('试算批次','中断后自动从未算完的观察续跑，已算过的观察不重复计入。')}
      ${runs.length ? runs.map(r => trialRunRow(r, expanded?.id === r.id)).join('') : empty('暂无试算批次。登记待启用版本后可创建。')}</section>
      ${expanded ? trialDetail(expanded) : ''}</div></div>`;
}
