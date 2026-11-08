"""Сборка самодостаточного HTML-дашборда мониторинга (Chart.js из CDN, данные встроены в страницу)."""
import json
from pathlib import Path

TEMPLATE = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Мониторинг кредитных моделей</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{
  color-scheme: light;
  --bg:#f4f4f2; --surface:#fcfcfb; --border:#e3e2dd; --text:#0b0b0b; --text2:#52514e; --muted:#7a7974;
  --s1:#2a78d6; --s2:#eb6834; --band:rgba(42,120,214,.07); --grid:#ecebe7;
  --good:#0ca30c; --warn:#fab219; --crit:#d03b3b; --grey:#9a9993;
}
@media (prefers-color-scheme: dark){
  :root:where(:not([data-theme="light"])){
    color-scheme: dark;
    --bg:#111110; --surface:#1a1a19; --border:#2e2e2b; --text:#f0efec; --text2:#c3c2b7; --muted:#8e8d86;
    --s1:#3987e5; --s2:#d95926; --band:rgba(57,135,229,.12); --grid:#2a2a27;
  }
}
:root[data-theme="dark"]{
  color-scheme: dark;
  --bg:#111110; --surface:#1a1a19; --border:#2e2e2b; --text:#f0efec; --text2:#c3c2b7; --muted:#8e8d86;
  --s1:#3987e5; --s2:#d95926; --band:rgba(57,135,229,.12); --grid:#2a2a27;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:24px 16px 48px}
header h1{font-size:24px;margin:0 0 4px}
header p{margin:0;color:var(--text2);font-size:14px}
.tabs{display:flex;gap:6px;margin:20px 0 16px;flex-wrap:wrap}
.tab{border:1px solid var(--border);background:var(--surface);color:var(--text);padding:8px 14px;border-radius:8px;cursor:pointer;font:inherit;display:flex;align-items:center;gap:8px}
.tab[aria-selected="true"]{border-color:var(--s1);box-shadow:inset 0 -2px 0 var(--s1);font-weight:600}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block;flex:none}
.g{background:var(--good)} .a{background:var(--warn)} .r{background:var(--crit)} .n{background:var(--grey)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px 18px;font-size:13px;color:var(--text2)}
.meta b{display:block;color:var(--text);font-size:14px;font-weight:600;overflow-wrap:anywhere}
.meta a{color:var(--s1)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:14px 0}
.kpi .lab{font-size:13px;color:var(--text2)}
.kpi .val{font-size:26px;font-weight:650;margin-top:4px;font-variant-numeric:tabular-nums}
.kpi .sub{font-size:13px;color:var(--muted);margin-top:2px}
.lights{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin-bottom:14px}
.light{display:flex;gap:10px;align-items:flex-start}
.light .dot{margin-top:5px}
.light .t{font-size:13px;color:var(--text2)} .light .v{font-weight:600}
.status{font-size:12px;color:var(--text2)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));gap:14px}
@media (max-width:560px){.grid{grid-template-columns:1fr}}
.chart h3{margin:0 0 2px;font-size:15px} .chart p{margin:0 0 8px;font-size:12.5px;color:var(--muted)}
.chart .box{position:relative;height:260px}
table{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}
th,td{padding:6px 8px;border-bottom:1px solid var(--border);text-align:right}
th:first-child,td:first-child{text-align:left}
th{color:var(--text2);font-weight:600}
.tablewrap{overflow-x:auto}
details{margin-top:14px} summary{cursor:pointer;color:var(--text2);font-size:14px}
footer{margin-top:28px;font-size:12.5px;color:var(--muted)}
.legend-note{font-size:12.5px;color:var(--muted);margin:2px 0 10px}
.band{display:inline-block;width:14px;height:10px;background:var(--band);border:1px solid var(--border);vertical-align:-1px}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>Мониторинг кредитных моделей: PD, LGD-12, LGD-24</h1>
  <p id="sub"></p>
</header>
<nav class="tabs" role="tablist" id="tabs"></nav>
<main id="panel"></main>
<footer id="foot"></footer>
</div>
<script>
const DATA = __DATA__;
const NAMES = {pd_model:'PD', lgd12_model:'LGD-12', lgd24_model:'LGD-24'};
const DESC = {
  pd_model:'Вероятность дефолта 90+ в первые 9 месяцев. Динамика по месяцу выдачи.',
  lgd12_model:'LGD-12 = 1 − чистое возмещение за 12 мес. / EAD. Прогноз на дату дефолта. Динамика по месяцу дефолта.',
  lgd24_model:'Прогноз чистого возмещения за 13–24 мес. после дефолта (модель на 12-й месяц). Динамика по месяцу дефолта.'
};
const LIGHT_TXT = {green:'В норме', amber:'Внимание', red:'Отклонение', grey:'Нет данных'};
const LIGHT_CLS = {green:'g', amber:'a', red:'r', grey:'n'};
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const pct = (v,d=1) => v==null ? '—' : (v*100).toFixed(d).replace('.',',')+' %';
const num = (v,d=2) => v==null ? '—' : v.toFixed(d).replace('.',',');
const int = v => v==null ? '—' : Math.round(v).toLocaleString('ru-RU');
let charts = [];

document.getElementById('sub').textContent =
  `Отчёт сформирован ${DATA.generated}. Данные: условный (синтетический) портфель потребкредитов. ` +
  `Модели загружены из MLflow Model Registry.`;
const T = DATA.thresholds, d = v => String(v).replace('.',',');
document.getElementById('foot').innerHTML =
  `Пороги светофора (внимание / отклонение): падение Gini тест к обучению > ${T.gini_drop[0]*100} % / > ${T.gini_drop[1]*100} %; ` +
  `PSI > ${d(T.psi[0])} / > ${d(T.psi[1])}; |PD/DR − 1| > ${d(T.calib[0])} / > ${d(T.calib[1])}; ` +
  `|смещение LGD| > ${T.lgd_bias[0]*100} / > ${T.lgd_bias[1]*100} п. п.; Спирмен < ${d(T.spearman[0])} / < ${d(T.spearman[1])}; рост MAE тест к обучению > 25 % / > 50 %. ` +
  `Ранговые метрики по месяцам считаются при n ≥ 20.`;

function worst(lights){
  const order = ['red','amber','green','grey'];
  const vals = Object.values(lights).map(x=>x[1]);
  for (const c of order) if (vals.includes(c)) return c;
  return 'grey';
}

const tabs = document.getElementById('tabs');
Object.keys(NAMES).forEach((k,i)=>{
  const b = document.createElement('button');
  b.className='tab'; b.setAttribute('role','tab'); b.dataset.k=k;
  const w = worst(DATA.models[k].lights);
  b.innerHTML = `<span class="dot ${LIGHT_CLS[w]}" aria-hidden="true"></span>${NAMES[k]} <span class="status">${LIGHT_TXT[w]}</span>`;
  b.onclick = ()=>show(k);
  tabs.appendChild(b);
});

const bandPlugin = {
  id:'testband',
  beforeDraw(chart, args, opts){
    const {ctx, chartArea:a, scales:{x}} = chart;
    if (opts.from==null) return;
    const i0 = opts.from, n = chart.data.labels.length;
    const step = n>1 ? (x.getPixelForValue(1)-x.getPixelForValue(0)) : a.width;
    const left = Math.max(a.left, x.getPixelForValue(i0) - step/2);
    ctx.save(); ctx.fillStyle = css('--band'); ctx.fillRect(left, a.top, a.right-left, a.bottom-a.top);
    ctx.fillStyle = css('--muted'); ctx.font = '11px system-ui'; ctx.fillText('тест', left+6, a.top+12);
    ctx.restore();
  }
};
Chart.register(bandPlugin);

function lineChart(el, labels, series, testFrom, fmt, yOpts={}){
  const grid = css('--grid'), txt = css('--text2');
  const c = new Chart(el, {
    type:'line',
    data:{labels, datasets: series.map((s,i)=>({label:s.label, data:s.data, borderColor:css(i? '--s2':'--s1'),
      backgroundColor:css(i? '--s2':'--s1'), borderWidth:2, pointRadius:2.5, pointHoverRadius:5, spanGaps:true, tension:.2,
      borderDash: s.dash ? [5,4] : []}))},
    options:{responsive:true, maintainAspectRatio:false, interaction:{mode:'index', intersect:false},
      plugins:{testband:{from:testFrom},
        legend:{display:series.length>1, labels:{color:txt, boxWidth:14, boxHeight:2}},
        tooltip:{callbacks:{label:ctx=>`${ctx.dataset.label}: ${fmt(ctx.parsed.y)}`}}},
      scales:{x:{ticks:{color:txt, maxRotation:0, autoSkip:true, maxTicksLimit:8}, grid:{display:false}},
              y:{ticks:{color:txt, callback:v=>fmt(v)}, grid:{color:grid}, ...yOpts}}}
  });
  charts.push(c);
}

function barChart(el, labels, data, testFrom, label){
  const c = new Chart(el, {type:'bar',
    data:{labels, datasets:[{label, data, backgroundColor:css('--s1'), borderRadius:4, maxBarThickness:18}]},
    options:{responsive:true, maintainAspectRatio:false, plugins:{testband:{from:testFrom}, legend:{display:false},
      tooltip:{callbacks:{label:ctx=>`${label}: ${int(ctx.parsed.y)}`}}},
      scales:{x:{ticks:{color:css('--text2'), maxRotation:0, autoSkip:true, maxTicksLimit:8}, grid:{display:false}},
              y:{ticks:{color:css('--text2')}, grid:{color:css('--grid')}, beginAtZero:true}}}});
  charts.push(c);
}

function chartCard(id, title, note){
  return `<div class="card chart"><h3>${title}</h3><p>${note}</p><div class="box"><canvas id="${id}"></canvas></div></div>`;
}

function show(k){
  charts.forEach(c=>c.destroy()); charts=[];
  document.querySelectorAll('.tab').forEach(t=>t.setAttribute('aria-selected', t.dataset.k===k));
  try{ localStorage.setItem('mon_tab',k); }catch(e){}
  const m = DATA.models[k], meta = m.meta, ov = m.overall, mon = m.monthly;
  const labels = mon.map(r=>r.month);
  const testFrom = mon.findIndex(r=>r.split==='test');
  const col = f => mon.map(r=>r[f]);

  let kpis = '', charts_html = '', table = '';
  if (m.kind==='pd'){
    kpis = [
      ['Gini, обучение → тест', `${num(ov.train.gini)} → ${num(ov.test.gini)}`, `KS на тесте ${num(ov.test.ks)}`],
      ['PD прогноз / DR факт (тест)', `${pct(ov.test.pd_pred)} / ${pct(ov.test.dr_actual)}`, `отношение ${num(ov.test.calib_ratio)}`],
      ['PSI скоринга (тест)', num(ov.test.psi,3), 'стабильность распределения PD'],
      ['Займов: обучение / тест', `${int(ov.train.n)} / ${int(ov.test.n)}`, `дефолтов ${int(ov.train.defaults)} / ${int(ov.test.defaults)}`]];
    charts_html =
      chartCard('c1','Прогноз PD и фактический уровень дефолтов','по месяцу выдачи') +
      chartCard('c2','Gini по месяцам','дискриминирующая способность; пропуски — месяцы с одним классом') +
      chartCard('c3','PSI к распределению обучающей выборки','> 0,10 — внимание, > 0,25 — значимый сдвиг') +
      chartCard('c4','Количество займов','по месяцу выдачи');
    table = ['n','defaults','dr_actual','pd_pred','calib_ratio','gini','ks','psi'];
  } else {
    const is24 = m.kind==='lgd24';
    const fl = is24 ? 'Возмещение мес. 13–24' : 'LGD-12';
    kpis = [
      [`${fl}: прогноз / факт (тест, взв. EAD)`, `${pct(ov.test.pred)} / ${pct(ov.test.fact)}`, `смещение ${num(ov.test.bias*100,1)} п. п.`],
      ['MAE, обучение → тест', `${num(ov.train.mae,3)} → ${num(ov.test.mae,3)}`, 'средняя абсолютная ошибка'],
      ['Спирмен (тест)', num(ov.test.spearman), 'ранговая связь прогноза и факта'],
      is24 ? ['Итоговый LGD-24: прогноз / факт (тест)', `${pct(ov.test.lgd24_pred)} / ${pct(ov.test.lgd24_fact)}`, '1 − RR₁₋₁₂ − прогноз']
           : ['Дефолтов: обучение / тест', `${int(ov.train.n)} / ${int(ov.test.n)}`, `EAD теста ${int(ov.test.ead)} BYN`]];
    charts_html =
      chartCard('c1',`${fl}: прогноз и факт`,'взвешено по EAD, по месяцу дефолта') +
      chartCard('c2','MAE по месяцам','средняя абсолютная ошибка') +
      chartCard('c3','Спирмен по месяцам','считается при n ≥ 20') +
      chartCard('c4','Количество дефолтов','по месяцу дефолта');
    table = is24 ? ['n','ead','fact','pred','bias','mae','spearman','lgd24_fact','lgd24_pred'] : ['n','ead','fact','pred','bias','mae','spearman'];
  }

  const lights = Object.entries(m.lights).map(([t,[v,c]])=>
    `<div class="card light"><span class="dot ${LIGHT_CLS[c]}" aria-hidden="true"></span><div>
      <div class="t">${t}</div><div class="v">${v==null?'—':(/падение|рост/.test(t)?(v>0?'+':'')+pct(v,0):num(v,3))} · ${LIGHT_TXT[c]}</div></div></div>`).join('');

  const fmtCell = (f,v) => v==null ? '—' : (['n','defaults'].includes(f) ? int(v) : f==='ead' ? int(v) :
      ['dr_actual','pd_pred','fact','pred','lgd24_fact','lgd24_pred'].includes(f) ? pct(v) : f==='bias' ? num(v*100,1)+' п. п.' : num(v,3));
  const thead = `<tr><th>Месяц</th><th>Выборка</th>${table.map(f=>`<th>${f}</th>`).join('')}</tr>`;
  const ovrows = ['train','test'].map(s=>`<tr><td><b>Итого</b></td><td>${s==='train'?'обучение':'тест'}</td>${table.map(f=>`<td>${fmtCell(f,ov[s][f])}</td>`).join('')}</tr>`).join('');
  const rows = mon.map(r=>`<tr><td>${r.month}</td><td>${r.split==='train'?'обучение':'тест'}</td>${table.map(f=>`<td>${fmtCell(f,r[f])}</td>`).join('')}</tr>`).join('');

  document.getElementById('panel').innerHTML = `
    <div class="card"><p style="margin:0 0 12px;color:var(--text2)">${DESC[k]}</p>
      <div class="meta">
        <div>Модель<b>${meta.name}</b></div><div>Версия<b>${meta.version}</b></div>
        <div>Алгоритм<b>${meta.algorithm||'—'}</b></div><div>Зарегистрирована<b>${meta.registered}</b></div>
        <div>Запуск MLflow<b>${meta.run_url?`<a href="${meta.run_url}" target="_blank" rel="noopener">${meta.run_name}</a>`:meta.run_name}</b></div>
        <div>Разбиение<b>${meta.oot_split||'—'}</b></div>
      </div></div>
    <div class="kpis">${kpis.map(([l,v,s])=>`<div class="card kpi"><div class="lab">${l}</div><div class="val">${v}</div><div class="sub">${s}</div></div>`).join('')}</div>
    <div class="lights">${lights}</div>
    <p class="legend-note"><span class="band"></span> — тестовый период (out-of-time). Наведите на график, чтобы увидеть значения.</p>
    <div class="grid">${charts_html}</div>
    <details><summary>Таблица метрик по месяцам</summary><div class="card tablewrap" style="margin-top:8px"><table>${thead}${ovrows}${rows}</table></div></details>`;

  if (m.kind==='pd'){
    lineChart('c1', labels, [{label:'Прогноз PD', data:col('pd_pred')}, {label:'Факт DR', data:col('dr_actual')}], testFrom, v=>pct(v), {beginAtZero:true});
    lineChart('c2', labels, [{label:'Gini', data:col('gini')}], testFrom, v=>num(v));
    lineChart('c3', labels, [{label:'PSI', data:col('psi')}], testFrom, v=>num(v,3), {beginAtZero:true});
    barChart('c4', labels, col('n'), testFrom, 'Займов');
  } else {
    lineChart('c1', labels, [{label:'Прогноз', data:col('pred')}, {label:'Факт', data:col('fact')}], testFrom, v=>pct(v), {min:0, max:1});
    lineChart('c2', labels, [{label:'MAE', data:col('mae')}], testFrom, v=>num(v,3), {beginAtZero:true});
    lineChart('c3', labels, [{label:'Спирмен', data:col('spearman')}], testFrom, v=>num(v));
    barChart('c4', labels, col('n'), testFrom, 'Дефолтов');
  }
}

let start = 'pd_model';
try{ const s = localStorage.getItem('mon_tab'); if (s && DATA.models[s]) start = s; }catch(e){}
show(start);
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', ()=>show(document.querySelector('.tab[aria-selected="true"]').dataset.k));
</script>
</body>
</html>
"""


def build_dashboard(payload, path):
    html = TEMPLATE.replace('__DATA__', json.dumps(payload, ensure_ascii=False).replace('</', '<\\/'))
    Path(path).write_text(html, encoding='utf8')
