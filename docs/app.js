const $ = id => document.getElementById(id);
const money = cents => new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' }).format(cents / 100);
const make = (tag, text, parent) => { const el = document.createElement(tag); el.textContent = text; parent.append(el); return el; };
const clear = el => el.replaceChildren();
let fixture = [], transactions = [], importEpoch = 0, fixtureLoaded = false, userData = false;
const BUDGET_MAX = 1000000;
function budgetCents() {
    const raw = $('budget').value.trim();
    if (raw === '')
        return null;
    const value = Number(raw);
    if (!Number.isFinite(value) || value < 0 || value > BUDGET_MAX)
        return null;
    const cents = Math.round(value * 100);
    return Number.isSafeInteger(cents) ? cents : null;
}
function validDate(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value))
        return false;
    const parsed = new Date(`${value}T00:00:00.000Z`);
    return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}
function validRow(row) {
    return typeof row.description === 'string' && row.description.trim() && row.description.length <= 200 &&
        typeof row.category === 'string' && row.category.trim() && row.category.length <= 80 &&
        validDate(row.date) &&
        Number.isSafeInteger(row.amount_cents) && Math.abs(row.amount_cents) <= 1000000000;
}
function options(id, items, all) {
    const select = $(id), previous = select.value;
    clear(select);
    if (all) {
        const option = new Option(all, 'all');
        select.add(option);
    }
    items.forEach(item => select.add(new Option(item, item)));
    select.value = [...select.options].some(option => option.value === previous) ? previous : (all ? 'all' : items[0] || '');
}
function setupFilters() {
    options('month', [...new Set(transactions.map(t => t.date.slice(0, 7)))].sort(), 'All months');
    const categories = [...new Set(transactions.map(t => t.category))].sort();
    options('category', categories, 'All categories');
    options('rule-category', categories, null);
}
function spending(rows) { return rows.reduce((sum, row) => sum + Math.max(0, -row.amount_cents), 0); }
function drawBars(id, entries) {
    const root = $(id);
    clear(root);
    if (!entries.length) {
        make('p', 'No spending in this selection.', root);
        return;
    }
    const max = Math.max(...entries.map(([, value]) => value), 1);
    entries.forEach(([label, value]) => {
        const row = make('div', '', root);
        row.className = 'bar-row';
        row.tabIndex = 0;
        row.setAttribute('role', 'group');
        row.setAttribute('aria-label', `${label}: ${money(value)}`);
        make('span', label, row);
        const track = make('span', '', row);
        track.className = 'track';
        const bar = make('span', '', track);
        bar.className = 'fill';
        bar.style.width = `${Math.max(1, 100 * value / max)}%`;
        make('strong', money(value), row);
    });
}
function recurring(rows) {
    const groups = new Map();
    rows.filter(row => row.amount_cents < 0).forEach(row => {
        const key = row.description.trim().toLocaleLowerCase();
        if (!groups.has(key))
            groups.set(key, []);
        groups.get(key).push(row);
    });
    const root = $('recurring');
    clear(root);
    const list = make('ul', '', root);
    list.className = 'list';
    for (const charges of groups.values()) {
        const months = new Set(charges.map(row => row.date.slice(0, 7)));
        const amounts = charges.map(row => -row.amount_cents), average = amounts.reduce((a, b) => a + b, 0) / amounts.length;
        if (months.size >= 3 && Math.max(...amounts) - Math.min(...amounts) <= Math.max(100, average * .1)) {
            make('li', `${charges[0].description}: ${months.size} distinct months, around ${money(average)}. Possible subscription; verify manually.`, list);
        }
    }
    if (!list.childElementCount)
        make('p', 'No candidate has three distinct months at similar amounts.', root);
}
function render() {
    const rows = transactions.filter(t => ($('month').value === 'all' || t.date.startsWith($('month').value)) &&
        ($('category').value === 'all' || t.category === $('category').value));
    const total = spending(rows);
    $('total').textContent = money(total);
    const budget = budgetCents(), alert = $('budget-alert');
    if (budget === null)
        alert.textContent = `Enter a monthly budget from 0 to ${BUDGET_MAX.toLocaleString('en-GB')} GBP.`;
    else if ($('month').value === 'all')
        alert.textContent = 'Choose a month to compare spending against the monthly budget.';
    else
        alert.textContent = total > budget ? `Over budget by ${money(total - budget)}.` : `${money(budget - total)} remaining in this selection.`;
    alert.className = alert.textContent.startsWith('Over') ? 'error' : 'muted';
    const grouped = field => [...rows.filter(t => t.amount_cents < 0).reduce((map, t) => map.set(field(t), (map.get(field(t)) || 0) - t.amount_cents), new Map())];
    drawBars('monthly', grouped(t => t.date.slice(0, 7)).sort());
    drawBars('categories', grouped(t => t.category).sort((a, b) => b[1] - a[1]));
    recurring(rows);
    const table = $('transactions');
    clear(table);
    rows.slice().sort((a, b) => b.date.localeCompare(a.date)).forEach(t => {
        const tr = make('tr', '', table);
        [t.date, t.description, t.category, money(t.amount_cents)].forEach((value, i) => {
            const cell = make('td', value, tr);
            if (i === 3)
                cell.className = 'num';
        });
    });
    if (!rows.length) {
        const row = make('tr', '', table);
        const cell = make('td', 'No matching transactions.', row);
        cell.colSpan = 4;
    }
    $('status').textContent = `${rows.length} of ${transactions.length} browser-only transactions shown.`;
}
function parseCSV(text) {
    const records = [], rows = [];
    let cells = [], field = '', quoted = false;
    for (let i = 0; i < text.length; i++) {
        const c = text[i];
        if (c === '"') {
            if (quoted && text[i + 1] === '"') {
                field += '"';
                i++;
            }
            else if (quoted || field === '')
                quoted = !quoted;
            else
                throw Error('Unexpected quote.');
        }
        else if (c === ',' && !quoted) {
            cells.push(field);
            field = '';
        }
        else if ((c === '\n' || c === '\r') && !quoted) {
            if (c === '\r' && text[i + 1] === '\n')
                i++;
            cells.push(field);
            field = '';
            if (cells.some(v => v.trim()))
                records.push(cells);
            cells = [];
            if (records.length > 5001)
                throw Error('Maximum 5,000 data rows.');
        }
        else
            field += c;
    }
    if (quoted)
        throw Error('Unclosed quoted value.');
    cells.push(field);
    if (cells.some(v => v.trim()))
        records.push(cells);
    if (!records.length || records[0].join(',').replace(/^﻿/, '').trim() !== 'date,description,amount_cents,category')
        throw Error('Expected exact headers: date,description,amount_cents,category.');
    if (records.length < 2 || records.length > 5001)
        throw Error('Supply 1 to 5,000 data rows.');
    for (const [index, cells] of records.slice(1).entries()) {
        if (cells.length !== 4 || !/^-?\d+$/.test(cells[2].trim()))
            throw Error(`Invalid CSV row ${index + 2}.`);
        const row = { id: index + 1, date: cells[0].trim(), description: cells[1].trim(), amount_cents: Number(cells[2].trim()), category: cells[3].trim() };
        if (!validRow(row))
            throw Error(`Invalid CSV row ${index + 2}.`);
        rows.push(row);
    }
    return rows;
}
$('month').addEventListener('change', render);
$('category').addEventListener('change', render);
$('budget').addEventListener('input', render);
$('apply-rule').addEventListener('click', () => {
    const pattern = $('rule-pattern').value.trim().toLocaleLowerCase(), category = $('rule-category').value;
    if (!pattern || !category) {
        $('rule-status').textContent = 'Enter a pattern and choose a category.';
        return;
    }
    let count = 0;
    transactions = transactions.map(row => row.description.toLocaleLowerCase().includes(pattern) ? (count++, { ...row, category }) : row);
    $('rule-status').textContent = `Reclassified ${count} matching transactions locally.`;
    setupFilters();
    render();
});
$('reset').addEventListener('click', () => { importEpoch++; userData = false; $('budget').value = '1200'; $('csv-file').value = ''; if (!fixtureLoaded) {
    $('import-status').textContent = 'Synthetic fixture is still loading; restore is unavailable yet.';
    return;
} transactions = fixture.map(row => ({ ...row })); $('import-status').textContent = 'Synthetic fixture restored.'; setupFilters(); render(); });
$('csv-file').addEventListener('change', async (event) => {
    const file = event.target.files[0];
    if (!file)
        return;
    const epoch = ++importEpoch;
    try {
        if (file.size > 1048576)
            throw Error('File exceeds 1 MiB.');
        const parsed = parseCSV(await file.text());
        if (epoch !== importEpoch)
            return;
        transactions = parsed;
        userData = true;
        setupFilters();
        render();
        $('import-status').textContent = `${parsed.length} rows processed locally. Restore fixture to discard them.`;
    }
    catch (error) {
        if (epoch === importEpoch)
            $('import-status').textContent = `Import rejected in full: ${error.message}`;
    }
    if (epoch === importEpoch)
        event.target.value = '';
});
fetch('./demo-data.json').then(response => { if (!response.ok)
    throw Error('Fixture unavailable.'); return response.json(); }).then(data => {
    if (!Array.isArray(data.transactions) || !data.transactions.length || !data.transactions.every(validRow))
        throw Error('Fixture rows invalid.');
    fixture = data.transactions.map(row => ({ ...row }));
    fixtureLoaded = true;
    if (userData)
        return;
    transactions = fixture.map(row => ({ ...row }));
    setupFilters();
    render();
}).catch(error => { if (!userData) {
    $('status').textContent = `Cannot load spending fixture: ${error.message} Try reloading the page.`;
    $('status').className = 'status error';
} });
function labelScrollableContent() {
    document.querySelectorAll('.scroll, pre').forEach(node => {
        node.tabIndex = 0;
        if (!node.hasAttribute('role'))
            node.setAttribute('role', 'region');
        if (!node.hasAttribute('aria-label'))
            node.setAttribute('aria-label', `${node.closest('section')?.querySelector('h2')?.textContent || 'Recorded'} scrollable content`);
    });
}
new MutationObserver(labelScrollableContent).observe(document.getElementById('main'), { childList: true, subtree: true });
labelScrollableContent();
