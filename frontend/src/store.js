export const state = {
  token: sessionStorage.getItem('zhaohui-token'), user:null, unit:'',
  observationResident:'', supplement:null, includeClosed:false, renderVersion:0,
};

export function setSession(token, user) {
  state.token = token;
  state.user = user;
  state.unit = '';
  state.observationResident = '';
  state.supplement = null;
  state.includeClosed = false;
  if (token) sessionStorage.setItem('zhaohui-token', token);
  else sessionStorage.removeItem('zhaohui-token');
}

export async function api(path, method='GET', data) {
  const headers = {};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  if (data !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(`/api${path}`, {method,headers,body:data === undefined ? undefined : JSON.stringify(data)});
  if (response.status === 401 && path !== '/auth/login') {
    setSession(null, null);
    window.dispatchEvent(new Event('staff-session-expired'));
  }
  const result = await response.json();
  if (!response.ok) throw new Error(`${result.detail || '请求失败'}${result.fields?.length ? `（${result.fields.join('、')}）` : ''}`);
  return result;
}
