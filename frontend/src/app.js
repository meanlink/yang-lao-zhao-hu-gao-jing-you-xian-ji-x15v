import {api, setSession, state} from './store.js';
import {brand, escape, ROLES, signalValues} from './shared.js';
import {alertsPage} from './alerts.js';
import {residentsPage} from './residents.js';
import {observationsPage} from './observations.js';
import {handoversPage} from './handovers.js';
import {careOperationsActions, contactsPage, followupsPage, responsesPage} from './careOperations.js';
import {coverageActions, shiftCoveragePage} from './shiftCoverage.js';
import {checkActions, responseChecksPage} from './responseChecks.js';

const app = document.querySelector('#app');
const notice = document.querySelector('#notification');
const routes = {alerts:['告警队列',alertsPage], residents:['住户档案',residentsPage], observations:['照护观察',observationsPage], handovers:['交班记录',handoversPage], responses:['照护响应',responsesPage], coverage:['值班覆盖',shiftCoveragePage], checks:['处置核对',responseChecksPage], contacts:['家属联络',contactsPage], followups:['交班后复查',followupsPage]};
let noticeTimeout;

function inform(message, failed=false) {
  clearTimeout(noticeTimeout);
  notice.textContent = message;
  notice.className = failed ? 'error visible' : 'visible';
  noticeTimeout = setTimeout(() => { notice.className = ''; }, 4700);
}

function loginView() {
  return `<main class="login-layout"><section class="login-intro">${brand()}<div class="login-copy"><p class="overline">朝晖长者照护中心</p><h1>把本班的事，<br>交代清楚。</h1><p>记录关键观察、复核告警优先级、签收接续事项。</p></div>
    <div class="shift-line"><span>观察录入</span><span>值班长复核</span><span>下一班签收</span></div></section>
    <section class="login-panel"><div><h2>值班登录</h2><p>使用照护中心的班组账号。</p><form data-do="login" class="stack">
    <label>账号<input type="email" name="email" autocomplete="username" required></label>
    <label>密码<input type="password" name="password" autocomplete="current-password" required></label>
    <button type="submit" class="primary">进入工作台</button></form><div class="demo"><p>演示账号</p><div>${Object.entries(ROLES).map(([key,label])=>`<button type="button" class="secondary" data-action="demo" data-value="${key}">${label}</button>`).join('')}</div></div></div></section></main>`;
}

function currentRoute() {
  const [key, id] = location.hash.slice(1).split('/');
  return Object.hasOwn(routes,key) ? [key,/^[0-9]+$/.test(id || '') ? Number(id) : null] : ['alerts', null];
}

async function render() {
  const version = ++state.renderVersion;
  if (!state.user) { app.innerHTML = loginView(); return; }
  const [key, id] = currentRoute();
  const sidebar = `<aside class="sidebar">${brand()}<nav aria-label="业务模块">${Object.entries(routes).map(([route,[label]])=>`<a href="#${route}" ${route===key ? 'aria-current="page"' : ''}><span class="nav-pin" aria-hidden="true"></span>${label}</a>`).join('')}</nav>
  <div class="profile"><span class="staff-monogram" aria-hidden="true">${escape(state.user.name.slice(0,1))}</span><div><strong>${escape(state.user.name)}</strong><small>${ROLES[state.user.role]}</small></div><button type="button" class="text-link" data-action="logout">退出</button></div></aside>`;
  const header = `<div class="topline"><span>朝晖长者照护中心 <span class="top-divider">/</span> ${routes[key][0]}</span><span>东翼 · 西翼 <span class="top-divider">/</span> 值班记录</span></div>`;
  try {
    const content = await routes[key][1](state, id);
    if (version === state.renderVersion) app.innerHTML = `<div class="shell">${sidebar}<main>${header}<div class="main-area">${content}</div></main></div>`;
  } catch (error) {
    if (version === state.renderVersion) app.innerHTML = `<div class="shell">${sidebar}<main>${header}<div class="main-area"><div class="note warn" role="alert">${escape(error.message)} <button type="button" class="secondary" data-action="refresh">重试</button></div></div></main></div>`;
  }
}

const actions = {
  ...careOperationsActions,
  ...coverageActions,
  ...checkActions,
  async login(_form, data) {
    const session = await api('/auth/login','POST',Object.fromEntries(data));
    setSession(session.access_token,session.user);
  },
  async register(_form,data) { await api('/residents','POST',Object.fromEntries(data)); return '住户档案已登记'; },
  async observe(_form,data) {
    const result = await api('/observations','POST',{...signalValues(data), ref:data.get('ref'), author_note:data.get('author_note'), resident_id:Number(data.get('resident_id'))});
    return result.status === 'incomplete' ? '观察已保存，需补齐关键字段' : '观察已保存，分级任务已入队';
  },
  async supplement(form,data) {
    const result = await api(`/observations/${form.dataset.id}/supplement`,'PATCH',signalValues(data));
    state.supplement = null;
    return result.status === 'incomplete' ? '已保存补录，仍有字段待核对' : '补录完成，已排队分级';
  },
  async review(form,data) {
    await api(`/alerts/${form.dataset.id}/review`,'POST',{revision:Number(form.dataset.revision),priority:Number(data.get('priority')),note:data.get('note')});
    return '告警已复核，可以提交交班';
  },
  async dispatch(form,data) {
    await api(`/alerts/${form.dataset.id}/handover`,'POST',{revision:Number(form.dataset.revision),...Object.fromEntries(data)});
    location.hash = '#handovers';
    return '已提交交班，等待接班员签收';
  },
  async sign(form,data) {
    await api(`/handovers/${form.dataset.id}/sign`,'POST',Object.fromEntries(data));
    return '签收完成，告警已交接';
  },
};

app.addEventListener('submit',async event=>{
  const form = event.target;
  const action = actions[form.dataset.do];
  if (!action) return;
  event.preventDefault();
  const submit = form.querySelector('button[type=submit]');
  submit.disabled = true;
  const route = location.hash;
  try {
    const message = await action(form,new FormData(form));
    if (message) inform(message);
    if (route === location.hash) await render();
  }
  catch (error) { inform(error.message,true); }
  finally { submit.disabled = false; }
});
app.addEventListener('click',event=>{
  const target = event.target.closest('[data-action]');
  if (!target) return;
  const {action,value} = target.dataset;
  if (action === 'demo') {
    const form = app.querySelector('form');
    form.elements.email.value = `${value}@zhaohui.local`;
    form.elements.password.value = 'zhaohui-demo';
    form.requestSubmit();
    return;
  }
  if (action === 'logout') {
    setSession(null,null);
    clearTimeout(noticeTimeout);
    notice.className = '';
    history.replaceState(null,'','#alerts');
  }
  if (action === 'unit') state.unit = value;
  if (action === 'supplement') state.supplement = Number(value);
  if (action === 'cancel-supplement') state.supplement = null;
  if (action === 'resident-observations') {
    state.observationResident = value;
    state.supplement = null;
    location.hash = '#observations';
    return;
  }
  render();
});
app.addEventListener('change',event=>{
  const node = event.target;
  if (node.dataset.change === 'observation-resident') { state.observationResident = node.value; state.supplement = null; render(); }
  if (node.dataset.change === 'include-closed') { state.includeClosed = node.checked; render(); }
});
window.addEventListener('hashchange',()=>{ window.scrollTo(0,0); render(); });
window.addEventListener('staff-session-expired',()=>{ inform('会话已失效，请重新登录',true); render(); });
if (state.token) {
  try { state.user = await api('/auth/me'); }
  catch (error) { if (state.token) inform(error.message,true); }
}
render();
