'use strict';
// Browser data comes only from this local API. Never interpolate statement text as HTML.
const $ = id => document.getElementById(id);
const state = {month: '', page: 1, pageSize: 25, categories: [], total: 0, view: 'overview', rules: [], requests: {}};
const money = pennies => new Intl.NumberFormat('en-GB', {style: 'currency', currency: 'GBP'}).format(pennies / 100);
function node(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function empty(id, message) { $(id).replaceChildren(node('p', message, 'empty')); }
function button(label, action, className = 'button ghost') {
  const el = node('button', label, className); el.type = 'button'; el.addEventListener('click', action); return el;
}
function status(message, error = false) {
  $('status').textContent = message; $('status').className = error ? 'status error' : 'status'; $('status').hidden = false;
}
async function api(path, options = {}) {
  const response = await fetch('/api' + path, options);
  const data = await response.json();
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map(x => x.msg).join('; ') : data.detail;
    const error = new Error(detail || 'The local request failed'); error.diagnostics = data.diagnostics; throw error;
  }
  return data;
}
const jsonOptions = (method, data) => ({method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
function show(view) {
  state.view = ['overview', 'transactions', 'recurring', 'budgets', 'rules', 'import'].includes(view) ? view : 'overview';
  document.querySelectorAll('.screen').forEach(el => el.hidden = el.id !== state.view);
  document.querySelectorAll('.sidebar nav a').forEach(el => {
    const active = el.hash === '#' + state.view; el.classList.toggle('active', active);
    if (active) el.setAttribute('aria-current', 'page'); else el.removeAttribute('aria-current');
  });
  $('topbar-section').textContent = state.view.toUpperCase();
  loadView().catch(error => status(error.message, true));
}
function optionList(select, values, first) {
  const previous = select.value; select.replaceChildren();
  if (first) { const opt = node('option', first); opt.value = ''; select.append(opt); }
  for (const value of values) { const opt = node('option', value); opt.value = value; select.append(opt); }
  if (values.includes(previous)) select.value = previous;
}
async function refresh(selectLatest = false) {
  const [meta, months] = await Promise.all([api('/meta'), api('/months')]);
  state.categories = meta.categories;
  if (selectLatest || !state.month) state.month = months[0] || new Date().toISOString().slice(0, 7);
  if (!months.includes(state.month)) months.unshift(state.month);
  optionList($('month'), months); $('month').value = state.month;
  $('month-note').textContent = meta.rows ? `${meta.first_date} to ${meta.last_date} · GBP assumed · historical` : 'No statement imported · GBP assumed';
  optionList($('category-filter'), state.categories, 'All categories');
  optionList($('budget-category'), state.categories, 'Choose a category');
  optionList($('rule-category'), state.categories, 'Choose a category');
  $('budget-month').value = state.month;
  await loadView();
}
async function loadView() {
  const view = state.view, token = (state.requests[view] || 0) + 1; state.requests[view] = token;
  const current = () => state.requests[view] === token;
  const errorBox = $(view + '-error'); if (errorBox) errorBox.hidden = true;
  try {
    if (view === 'overview') {
      const data = await api('/summary?month=' + state.month); if (!current()) return; renderSummary(data);
    } else if (view === 'transactions') {
      const params = new URLSearchParams({month: state.month, search: $('search').value, category: $('category-filter').value, page: state.page, page_size: state.pageSize});
      const data = await api('/transactions?' + params); if (!current()) return; renderTransactions(data);
    } else if (view === 'recurring') {
      const data = await api('/recurring'); if (!current()) return; renderRecurring(data);
    } else if (view === 'budgets') {
      const data = await api('/budgets?month=' + state.month); if (!current()) return; renderBudgets(data);
    } else if (view === 'rules') {
      const data = await api('/rules'); if (!current()) return; state.rules = data; renderRules(data);
    } else if (view === 'import') {
      const data = await api('/imports'); if (!current()) return; renderImports(data);
    }
  } catch (error) {
    if (current() && errorBox) { errorBox.textContent = error.message; errorBox.hidden = false; }
    throw error;
  }
}
function renderSummary(data) {
  $('metrics').replaceChildren();
  for (const [label, key, detail] of [['Money in', 'income_pence', 'All recorded credits'], ['Money out', 'outflow_pence', 'All recorded debits'], ['Spending', 'spending_pence', 'Excludes savings and transfers'], ['Moved aside', 'transfers_pence', 'Savings and transfer debits']]) {
    const card = node('article', undefined, 'metric' + (key === 'spending_pence' ? ' primary' : ''));
    card.append(node('p', label, 'metric-label'), node('p', money(data[key]), 'metric-value'), node('small', detail)); $('metrics').append(card);
  }
  if (!data.rows) { empty('categories', 'No records for this month. Import a statement or choose another month.'); empty('trends', 'Import a statement to explore historical cashflow.'); return; }
  $('categories').replaceChildren();
  const maximum = Math.max(...data.categories.map(x => x.amount_pence), 1);
  for (const item of data.categories) {
    const row = node('div', undefined, 'bar-row'); row.tabIndex = 0; row.setAttribute('role', 'button');
    row.setAttribute('aria-label', `${item.category}: ${money(item.amount_pence)}. Show transactions.`);
    const label = node('div', undefined, 'bar-label'); label.append(node('span', item.category), node('strong', money(item.amount_pence)));
    const track = node('div', undefined, 'bar-track'), fill = node('div', undefined, 'bar-fill'); fill.style.width = (100 * item.amount_pence / maximum) + '%'; track.append(fill); row.append(label, track);
    const open = () => { $('category-filter').value = item.category; state.page = 1; location.hash = 'transactions'; };
    row.addEventListener('click', open); row.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } }); $('categories').append(row);
  }
  if (!data.categories.length) empty('categories', 'This month contains no categorized spending.');
  const trends = data.trends.filter(x => x.month <= state.month).slice(-12);
  $('trends').replaceChildren(node('p', 'Up to twelve months ending at the selected month. Credits and all debits; historical GBP.', 'empty'));
  const table = node('table', undefined, 'mini-table'), head = node('thead'), tr = node('tr');
  for (const label of ['Month', 'In', 'Out', 'Net']) { const th = node('th', label); th.scope = 'col'; tr.append(th); } head.append(tr); table.append(head);
  const tbody = node('tbody');
  for (const trend of trends) { const row = node('tr'); for (const value of [trend.month, money(trend.income_pence), money(trend.outflow_pence), money(trend.income_pence - trend.outflow_pence)]) row.append(node('td', value)); tbody.append(row); }
  table.append(tbody); $('trends').append(table);
}
function renderTransactions(data) {
  state.total = data.total; $('transaction-rows').replaceChildren();
  for (const item of data.items) {
    const tr = node('tr'); tr.append(node('td', item.date)); const description = node('td'); description.append(node('strong', item.description), node('small', item.transaction_type || 'Blank type'));
    const category = node('td'); category.append(node('strong', item.category), node('small', item.reason));
    const amount = node('td', money(item.amount_pence), 'numeric ' + (item.amount_pence > 0 ? 'amount-in' : 'amount-out'));
    const control = node('td'), select = node('select'); select.setAttribute('aria-label', 'Override category for ' + item.description);
    optionList(select, [...new Set([...state.categories, item.category])], 'Use rules'); select.value = item.override_category || '';
    select.addEventListener('change', async () => { select.disabled = true; try { await api('/transactions/' + item.id, jsonOptions('PATCH', {category: select.value || null})); status('Category updated.'); await refresh(); } catch (error) { status(error.message, true); select.disabled = false; } });
    control.append(select); tr.append(description, category, amount, control); $('transaction-rows').append(tr);
  }
  if (!data.items.length) { const row = node('tr'), cell = node('td', 'No matching transactions for ' + state.month + '.', 'empty'); cell.colSpan = 5; row.append(cell); $('transaction-rows').append(row); }
  $('transaction-count').textContent = data.total + ' matching entries · ' + state.month; $('page-label').textContent = 'Page ' + data.page;
  $('prev-page').disabled = data.page <= 1; $('next-page').disabled = data.page * data.page_size >= data.total;
}
function renderRecurring(items) {
  $('recurring-list').replaceChildren();
  for (const item of items) {
    const card = node('article', undefined, 'pattern-card');
    card.append(node('p', item.cadence.toUpperCase() + ' CANDIDATE', 'eyebrow'), node('h2', item.description), node('p', money(item.amount_pence), 'pattern-amount'),
      node('p', `${item.observations} distinct dates · ${Math.round(item.cadence_consistency * 100)}% of gaps match · ±${item.day_tolerance} days`),
      node('p', 'Observed: ' + item.evidence_dates.join(', '), 'pattern-dates'), node('p', item.uncertainty, 'pattern-uncertainty'));
    $('recurring-list').append(card);
  }
  if (!items.length) empty('recurring-list', 'No sufficiently regular candidates. Three distinct dates and stable amounts are required.');
}
function renderBudgets(items) {
  $('alerts-list').replaceChildren(); $('budgets-list').replaceChildren();
  for (const item of items) {
    const row = node('div', undefined, 'record'), content = node('div');
    content.append(node('strong', item.category + ' · ' + money(item.limit_pence)), node('small', state.month + ' · alert at ' + item.threshold_percent + '% · spent ' + money(item.spent_pence)));
    row.append(content, button('Delete', async () => { try { await api('/budgets/' + item.id, {method: 'DELETE'}); await loadView(); status('Budget removed.'); } catch (error) { status(error.message, true); } }, 'button danger')); $('budgets-list').append(row);
    if (item.alert) { const alert = node('div', undefined, 'alert-item ' + item.state); alert.append(node('strong', item.category + ': ' + (item.state === 'over' ? 'over budget' : 'threshold reached')), node('small', money(item.spent_pence) + ' of ' + money(item.limit_pence) + ' · ' + state.month)); $('alerts-list').append(alert); }
  }
  if (!items.length) empty('budgets-list', 'No saved category budgets for ' + state.month + '.');
  if (!items.some(x => x.alert)) empty('alerts-list', 'No budget thresholds reached for ' + state.month + '. Alerts stay in this local workspace.');
}
function resetRule() { $('rule-form').reset(); $('rule-id').value = ''; $('rule-type').value = ''; $('rule-cancel').hidden = true; $('rule-submit').textContent = 'Save rule'; }
function renderRules(items) {
  $('rules-list').replaceChildren();
  for (const item of items) {
    const row = node('div', undefined, 'record'), info = node('div'), actions = node('div', undefined, 'record-actions');
    info.append(node('strong', (item.pattern || 'Any description') + ' → ' + item.category), node('small', 'Priority ' + item.priority + ' · ' + (item.transaction_type || 'any type') + ' · rule ' + item.id));
    actions.append(button('Edit', () => { $('rule-id').value = item.id; $('rule-pattern').value = item.pattern; $('rule-type').value = item.transaction_type; $('rule-category').value = item.category; $('rule-priority').value = item.priority; $('rule-cancel').hidden = false; $('rule-submit').textContent = 'Update rule'; $('rule-pattern').focus(); }),
      button('Delete', async () => { try { await api('/rules/' + item.id, {method: 'DELETE'}); await refresh(); status('Rule removed; existing entries reclassified.'); } catch (error) { status(error.message, true); } }, 'button danger'));
    row.append(info, actions); $('rules-list').append(row);
  }
  if (!items.length) empty('rules-list', 'No rules. Credits default to Income and unclassified debits to Other.');
}
function renderImports(items) {
  let container = $('import-history');
  if (!container) { container = node('div'); container.id = 'import-history'; $('import-form').after(container); }
  container.replaceChildren(node('h3', 'Imported statements'));
  for (const item of items) { const entry = node('div', undefined, 'record'), text = node('div'); text.append(node('strong', item.name + ' · ' + item.rows + ' rows'), node('small', item.created_at), node('small', 'SHA-256 ' + item.id)); entry.append(text); container.append(entry); }
  if (!items.length) container.append(node('p', 'No statements imported yet. The demo CSV is in data/prepared/moneyvis-demo.csv.', 'empty'));
}
// Add the explicit type condition supported by the domain engine to the preserved worker form.
const typeGroup = node('div'), typeLabel = node('label', 'TRANSACTION TYPE · OPTIONAL'); typeLabel.htmlFor = 'rule-type';
const typeInput = node('input'); typeInput.id = 'rule-type'; typeInput.maxLength = 20; typeInput.placeholder = 'e.g. DD; blank matches any type'; typeGroup.append(typeLabel, typeInput); $('rule-pattern').parentElement.after(typeGroup); $('rule-pattern').required = false;
$('budget-amount').min = '0'; $('budget-amount').max = '1000000000000';
$('month').addEventListener('change', async () => { state.month = $('month').value; state.page = 1; $('budget-month').value = state.month; try { await loadView(); } catch (error) { status(error.message, true); } });
$('transaction-filters').addEventListener('submit', e => { e.preventDefault(); state.page = 1; loadView().catch(error => status(error.message, true)); });
$('prev-page').addEventListener('click', () => { state.page--; loadView().catch(error => status(error.message, true)); });
$('next-page').addEventListener('click', () => { state.page++; loadView().catch(error => status(error.message, true)); });
$('budget-form').addEventListener('submit', async e => {
  e.preventDefault(); const submit = e.submitter; submit.disabled = true;
  try { const month = $('budget-month').value; await api('/budgets', jsonOptions('POST', {month, category: $('budget-category').value, limit_pence: Math.round(Number($('budget-amount').value) * 100), threshold_percent: Number($('budget-threshold').value)})); state.month = month; await refresh(); status('Budget saved for ' + month + '.'); } catch (error) { status(error.message, true); } finally { submit.disabled = false; }
});
$('rule-form').addEventListener('submit', async e => {
  e.preventDefault(); const submit = e.submitter; submit.disabled = true;
  try { const id = $('rule-id').value; await api('/rules' + (id ? '/' + id : ''), jsonOptions(id ? 'PUT' : 'POST', {pattern: $('rule-pattern').value, transaction_type: $('rule-type').value, category: $('rule-category').value, priority: Number($('rule-priority').value)})); resetRule(); await refresh(); status('Rule saved; existing entries reclassified, manual overrides preserved.'); } catch (error) { status(error.message, true); } finally { submit.disabled = false; }
});
$('rule-cancel').addEventListener('click', resetRule);
$('import-form').addEventListener('submit', async e => {
  e.preventDefault(); const file = $('csv-file').files[0]; if (!file) return; const submit = e.submitter; submit.disabled = true;
  $('import-result').hidden = false; $('import-result').className = 'import-result'; $('import-result').textContent = 'Validating the whole statement…';
  let committed = false;
  try { const form = new FormData(); form.append('file', file); const result = await api('/imports', {method: 'POST', body: form}); committed = true; $('import-result').replaceChildren(node('strong', `${result.inserted} inserted · ${result.duplicates} already imported`), node('p', 'Statement SHA-256: ' + result.sha256), node('p', result.blank_types + ' blank transaction types retained.')); await refresh(true); status('Statement processed atomically.'); }
  catch (error) {
    if (committed) { $('import-result').append(node('p', 'Statement committed, but refreshing the view failed. Reload to retry the view.')); status('Statement committed; view refresh failed: ' + error.message, true); }
    else { $('import-result').className = 'import-result error'; $('import-result').replaceChildren(node('strong', error.message)); for (const item of error.diagnostics || []) $('import-result').append(node('p', 'Row ' + item.row + ': ' + item.error)); status('Import failed; no rows from this file were added.', true); }
  }
  finally { submit.disabled = false; }
});
window.addEventListener('hashchange', () => show(location.hash.slice(1)));
refresh().then(() => show(location.hash.slice(1))).catch(error => status(error.message, true));
