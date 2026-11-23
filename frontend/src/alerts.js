import {api} from './store.js';
import {FEATURES, OBSERVATIONS, PRIORITIES, SHIFTS, button, empty, escape, heading, panel, priority, status, time} from './shared.js';

function resultBlock(observation, currentPriority) {
  const result = observation.result;
  if (!result) return '';
  const bars = Object.keys(PRIORITIES).reverse().map(level => {
    const percent = result.probabilities[level] * 100;
    return `<div class="meter-row"><span>${PRIORITIES[level]}</span><meter min="0" max="100" value="${percent}">${percent.toFixed(1)}%</meter><strong>${percent.toFixed(1)}%</strong></div>`;
  }).join('');
  return `<section class="analysis"><div class="analysis-heading"><h3>分级证据</h3><span>${escape(observation.ref)}</span></div>
    <p>本次候选 ${PRIORITIES[result.candidate]} · 对照 ${PRIORITIES[result.runner_up]}</p>
    ${result.candidate < currentPriority ? '<p class="missing">仍采用当前较高告警等级，直到交班签收。</p>' : ''}
    <div class="meters">${bars}</div>
    <dl class="contributions">${result.contributions.map(item => `<div><dt>${FEATURES[item.feature]} <span>${item.value ? '是' : '否'}</span></dt><dd>${item.log_odds >= 0 ? '+' : ''}${item.log_odds.toFixed(2)}</dd></div>`).join('')}</dl>
    <small>数值为各信号对候选与次选的对数赔率贡献。先验项 ${result.prior_log_odds.toFixed(2)}。模型 ${escape(result.model_checksum.slice(0,12))}。</small></section>`;
}

function detailBlock(row, canReview) {
  const scored = row.observations.find(obs => obs.status === 'scored');
  let action = '';
  if (row.status === 'incomplete') action = '<div class="note warn"><strong>关键观察待补</strong><p>当前优先级保留。全部缺项补录并完成分级后，值班长才可复核。</p><a href="#observations">打开照护观察</a></div>';
  if (row.status === 'evaluating') action = '<div class="note">观察正在分级。点击刷新查看最新结果。</div>';
  if (row.status === 'review' && canReview) action = `<form data-do="review" data-id="${row.id}" data-revision="${row.revision}" class="stack review-form">
    <h3>值班长复核</h3><label>确认优先级<select name="priority" required>${Object.entries(PRIORITIES).filter(([key])=>Number(key)>=row.priority).map(([key,val])=>`<option value="${key}">${val}</option>`).join('')}</select></label>
    <label>复核说明<input name="note" minlength="3" maxlength="600" required placeholder="填写核对结果或上调理由"></label>${button('确认告警')}</form>`;
  if (row.status === 'confirmed' && canReview && !row.active_response_id) action = `<form data-do="dispatch" data-id="${row.id}" data-revision="${row.revision}" class="stack review-form">
    <h3>提交交班</h3><label>接收班次<select name="target_shift">${Object.entries(SHIFTS).map(([key,val])=>`<option value="${key}" ${key === 'night' ? 'selected' : ''}>${val}</option>`).join('')}</select></label>
    <label>接续事项<input name="next_action" minlength="3" maxlength="600" required placeholder="填写下一班需要确认的事项"></label>${button('提交交班')}</form>`;
  return `${panel(`${row.room} · ${row.resident_name}`, `${row.code} · 告警 #${row.id} · 版本 ${row.revision}`)}
    <div class="detail-pad"><div class="data-line">${priority(row.priority)}${status(row.status)}</div>
    <div class="ops-links"><a class="secondary" href="#responses/${row.id}">照护响应派单</a><a class="secondary" href="#contacts/${row.id}">家属联络留痕</a></div>
    ${row.active_response_id ? '<div class="note warn">本条告警还有在办的照护响应任务，完成或撤销后方可交班。</div>' : ''}
    ${row.review_note ? `<div class="review-memo"><strong>${escape(row.reviewer_name)} · ${time(row.reviewed_at)}</strong><p>${escape(row.review_note)}</p></div>` : ''}
    ${action}${scored ? resultBlock(scored,row.priority) : ''}
    <section class="evidence-list"><h3>关联观察</h3>${row.observations.map(obs => `<div>${status(obs.status,OBSERVATIONS)} <strong>${escape(obs.ref)}</strong><p>${escape(obs.author_note)}</p></div>`).join('')}</section></div>`;
}

export async function alertsPage(state, activeId) {
  const rows = await api(`/alerts?include_closed=${state.includeClosed}`);
  const detail = activeId || rows.at(0)?.id;
  const selected = detail ? await api(`/alerts/${detail}`) : null;
  const urgent = rows.filter(r => r.priority === 3 && r.status !== 'closed').length;
  const missing = rows.filter(r => r.status === 'incomplete').length;
  const review = rows.filter(r => r.status === 'review').length;
  return `${heading('告警队列','本班优先处理','先处理高优先级告警，补齐观察后再复核与交班。', '<button class="secondary refresh" type="button" data-action="refresh">刷新队列</button>')}
    <div class="briefing"><div><strong>${urgent}</strong><span>优先处理</span></div><div><strong>${missing}</strong><span>待补观察</span></div><div><strong>${review}</strong><span>待值班长复核</span></div></div>
    <div class="split alert-split"><section class="paper">${panel('告警清单','按当前优先级和更新时间排序')}
    <div class="filter-row"><label><input type="checkbox" data-change="include-closed" ${state.includeClosed ? 'checked' : ''}>包含已交接</label></div>
    ${rows.length ? rows.map(r => `<a href="#alerts/${r.id}" class="queue-row ${r.id===selected?.id ? 'chosen' : ''}" ${r.id===selected?.id ? 'aria-current="true"' : ''}>
      <div class="data-line">${priority(r.priority)}${status(r.status)}</div><strong>${escape(r.room)} · ${escape(r.resident_name)}</strong>
      <span>${escape(r.unit)} · ${r.incomplete_count ? `${r.incomplete_count} 条观察待补` : time(r.updated_at)}</span></a>`).join('') : empty('当前没有在办告警。录入观察后可在此查看分级。')}
    </section><section class="paper detail">${selected ? detailBlock(selected,state.user.role==='lead') : empty('选择一条告警查看观察及分级证据。')}</section></div>`;
}
