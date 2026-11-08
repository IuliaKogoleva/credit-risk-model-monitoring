"""Self-contained HTML monitoring dashboard (Chart.js from CDN, data embedded in the page).

The page is bilingual (English / Russian): the language is taken from ``?lang=en|ru``,
then from the visitor's last choice, then from the browser language. Open Graph tags in
``<head>`` are static English text, so link previews (LinkedIn, Telegram, Slack) look the
same for everyone; ``preview.png`` next to the page is produced by ``src/preview.py``.
"""
import html
import json
from pathlib import Path

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Credit risk model monitoring: PD, LGD-12, LGD-24</title>
<meta name="description" content="__DESCRIPTION__">
<meta name="author" content="__AUTHOR__">
<meta property="og:type" content="website">
<meta property="og:title" content="Credit risk model monitoring: PD, LGD-12, LGD-24">
<meta property="og:description" content="__DESCRIPTION__">
<meta property="og:url" content="__SITE_URL__">
<meta property="og:image" content="__SITE_URL__preview.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="627">
<meta property="og:image:alt" content="Monitoring dashboard: traffic lights, Gini, PSI and calibration by month for PD and LGD models">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%232a78d6'/%3E%3Cpolyline points='6,22 12,15 17,19 26,9' fill='none' stroke='white' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
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
a{color:var(--s1)}
.wrap{max-width:1180px;margin:0 auto;padding:24px 16px 48px}
header{display:flex;gap:12px 24px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap}
header h1{font-size:24px;margin:0 0 4px}
header p{margin:0;color:var(--text2);font-size:14px}
.tools{display:flex;gap:10px;align-items:center;flex:none}
.lang{display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden;background:var(--surface)}
.lang button{border:0;background:none;color:var(--text2);font:inherit;font-size:13px;padding:6px 10px;cursor:pointer}
.lang button[aria-pressed="true"]{background:var(--s1);color:#fff;font-weight:600}
.src{font-size:13px;text-decoration:none;border:1px solid var(--border);border-radius:8px;padding:6px 10px;background:var(--surface);color:var(--text)}
.src:hover,.lang button:hover{border-color:var(--s1)}
.tabs{display:flex;gap:6px;margin:20px 0 16px;flex-wrap:wrap}
.tab{border:1px solid var(--border);background:var(--surface);color:var(--text);padding:8px 14px;border-radius:8px;cursor:pointer;font:inherit;display:flex;align-items:center;gap:8px}
.tab[aria-selected="true"]{border-color:var(--s1);box-shadow:inset 0 -2px 0 var(--s1);font-weight:600}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block;flex:none}
.g{background:var(--good)} .a{background:var(--warn)} .r{background:var(--crit)} .n{background:var(--grey)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px 18px;font-size:13px;color:var(--text2)}
.meta b{display:block;color:var(--text);font-size:14px;font-weight:600;overflow-wrap:anywhere}
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
@media (max-width:560px){.grid{grid-template-columns:1fr} header h1{font-size:21px}}
.chart h3{margin:0 0 2px;font-size:15px} .chart p{margin:0 0 8px;font-size:12.5px;color:var(--muted)}
.chart .box{position:relative;height:260px}
table{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}
th,td{padding:6px 8px;border-bottom:1px solid var(--border);text-align:right;white-space:nowrap}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}
th{color:var(--text2);font-weight:600}
.tablewrap{overflow-x:auto}
details{margin-top:14px} summary{cursor:pointer;color:var(--text2);font-size:14px}
footer{margin-top:28px;font-size:12.5px;color:var(--muted)}
footer p{margin:0 0 6px}
.legend-note{font-size:12.5px;color:var(--muted);margin:2px 0 10px}
.band{display:inline-block;width:14px;height:10px;background:var(--band);border:1px solid var(--border);vertical-align:-1px}
/* compact layout for the 1200x627 link-preview screenshot (?preview=1) */
body.preview .wrap{padding:18px 22px 0}
body.preview .meta-card,body.preview .legend-note,body.preview details,body.preview footer,body.preview .tools{display:none}
body.preview .tabs{margin:14px 0 12px}
body.preview .kpis{margin:0 0 12px}
body.preview .chart .box{height:178px}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div>
    <h1 id="title"></h1>
    <p id="sub"></p>
  </div>
  <div class="tools">
    <div class="lang" role="group" aria-label="Language">
      <button type="button" data-lang="en">EN</button><button type="button" data-lang="ru">RU</button>
    </div>
    <a class="src" id="src" target="_blank" rel="noopener"></a>
  </div>
</header>
<nav class="tabs" role="tablist" id="tabs"></nav>
<main id="panel"></main>
<footer id="foot"></footer>
</div>
<script>
const DATA = __DATA__;
const LINKS = DATA.links || {};
const NAMES = {pd_model:'PD', lgd12_model:'LGD-12', lgd24_model:'LGD-24'};
const LIGHT_CLS = {green:'g', amber:'a', red:'r', grey:'n'};

const I18N = {
  en: {
    locale:'en-GB',
    title:'Credit risk model monitoring: PD, LGD-12, LGD-24',
    sub:g=>`Report generated ${g}. Data: synthetic consumer-loan portfolio. Models loaded from MLflow Model Registry.`,
    source:'Source code',
    desc:{
      pd_model:'Probability of 90+ days past due within the first 9 months after issue. Monthly dynamics by issue month.',
      lgd12_model:'LGD-12 = 1 − net recoveries over 12 months / EAD, predicted at the default date. Monthly dynamics by default month.',
      lgd24_model:'Forecast of net recoveries in months 13–24 after default (model applied at month 12). Monthly dynamics by default month.'},
    light:{green:'OK', amber:'Warning', red:'Alert', grey:'No data'},
    lights:{gini_drop:'Gini drop, test vs train', psi:'Score PSI, test vs train', calib:'Calibration: |PD/DR − 1| (test)',
      lgd_bias:'Forecast bias (test), |pp|', spearman:'Spearman rank correlation (test)', mae_growth:'MAE growth, test vs train'},
    meta:['Model','Version','Algorithm','Registered','MLflow run','Out-of-time split'],
    algo:{logreg:'Logistic regression', ridge:'Ridge regression', hgb:'Gradient boosting'},
    split:s=>s.replace(/выдачи/g,'loans issued').replace(/дефолты/g,'defaults').replace(/ до /g,' before ')
              .replace(/после/g,'after').replace(/ с /g,' from '),
    pd:{kpi:[['Gini, train → test', o=>`KS (test) ${o.ks}`], ['Predicted PD / observed DR (test)', o=>`ratio ${o.ratio}`],
             ['Score PSI (test)','stability of the PD distribution'], ['Loans: train / test', o=>`defaults ${o.d}`]],
        charts:[['Predicted PD vs observed default rate','by issue month'],['Gini by month','discriminatory power; gaps are months with one class'],
                ['PSI vs train distribution','> 0.10 warning, > 0.25 significant shift'],['Number of loans','by issue month']],
        series:{pd:'Predicted PD', dr:'Observed DR', loans:'Loans'}},
    lgd:{fl12:'LGD-12', fl24:'Recoveries, months 13–24',
         kpi:{fact:fl=>`${fl}: predicted / actual (test, EAD-weighted)`, bias:b=>`bias ${b} pp`, mae:['MAE, train → test','mean absolute error'],
              sp:['Spearman (test)','rank correlation of forecast and actual'], l24:['Final LGD-24: predicted / actual (test)','1 − RR₁₋₁₂ − forecast'],
              n:['Defaults: train / test', e=>`test EAD ${e} BYN`]},
         charts:{c1:fl=>[`${fl}: predicted vs actual`,'EAD-weighted, by default month'], c2:['MAE by month','mean absolute error'],
                 c3:['Spearman by month','computed when n ≥ 20'], c4:['Number of defaults','by default month']},
         series:{pred:'Predicted', fact:'Actual', defaults:'Defaults'}},
    band:'test',
    note:'— out-of-time test period. Hover over a chart to see values.',
    table:'Monthly metrics table', month:'Month', sample:'Sample', total:'Total', train:'train', test:'test',
    cols:{n_pd:'Loans', n_lgd:'Defaults', defaults:'Defaults', dr_actual:'Observed DR', pd_pred:'Predicted PD', calib_ratio:'PD / DR',
          gini:'Gini', ks:'KS', psi:'PSI', ead:'EAD, BYN', fact:'Actual', pred:'Predicted', bias:'Bias, pp', mae:'MAE',
          spearman:'Spearman', lgd24_fact:'LGD-24 actual', lgd24_pred:'LGD-24 predicted'},
    pp:'pp',
    foot:T=>`Traffic-light thresholds (warning / alert): Gini drop test vs train > ${p0(T.gini_drop[0])} / > ${p0(T.gini_drop[1])}; `+
      `PSI > ${T.psi[0]} / > ${T.psi[1]}; |PD/DR − 1| > ${T.calib[0]} / > ${T.calib[1]}; `+
      `|LGD bias| > ${T.lgd_bias[0]*100} / > ${T.lgd_bias[1]*100} pp; Spearman < ${T.spearman[0]} / < ${T.spearman[1]}; `+
      `MAE growth test vs train > ${p0(T.mae_growth[0])} / > ${p0(T.mae_growth[1])}. Monthly rank metrics are computed when a month has n ≥ 20.`,
    author:'Author'
  },
  ru: {
    locale:'ru-RU',
    title:'Мониторинг кредитных моделей: PD, LGD-12, LGD-24',
    sub:g=>`Отчёт сформирован ${g}. Данные: условный (синтетический) портфель потребкредитов. Модели загружены из MLflow Model Registry.`,
    source:'Исходный код',
    desc:{
      pd_model:'Вероятность дефолта 90+ в первые 9 месяцев. Динамика по месяцу выдачи.',
      lgd12_model:'LGD-12 = 1 − чистое возмещение за 12 мес. / EAD. Прогноз на дату дефолта. Динамика по месяцу дефолта.',
      lgd24_model:'Прогноз чистого возмещения за 13–24 мес. после дефолта (модель на 12-й месяц). Динамика по месяцу дефолта.'},
    light:{green:'В норме', amber:'Внимание', red:'Отклонение', grey:'Нет данных'},
    lights:{gini_drop:'Gini, падение тест/обучение', psi:'PSI скоринга (тест к обучению)', calib:'Калибровка: |PD/DR − 1| (тест)',
      lgd_bias:'Смещение прогноза (тест), |п. п.|', spearman:'Ранговая связь Спирмена (тест)', mae_growth:'MAE: рост тест/обучение'},
    meta:['Модель','Версия','Алгоритм','Зарегистрирована','Запуск MLflow','Разбиение'],
    algo:{logreg:'Логистическая регрессия', ridge:'Гребневая регрессия', hgb:'Градиентный бустинг'},
    split:s=>s,
    pd:{kpi:[['Gini, обучение → тест', o=>`KS на тесте ${o.ks}`], ['PD прогноз / DR факт (тест)', o=>`отношение ${o.ratio}`],
             ['PSI скоринга (тест)','стабильность распределения PD'], ['Займов: обучение / тест', o=>`дефолтов ${o.d}`]],
        charts:[['Прогноз PD и фактический уровень дефолтов','по месяцу выдачи'],['Gini по месяцам','дискриминирующая способность; пропуски — месяцы с одним классом'],
                ['PSI к распределению обучающей выборки','> 0,10 — внимание, > 0,25 — значимый сдвиг'],['Количество займов','по месяцу выдачи']],
        series:{pd:'Прогноз PD', dr:'Факт DR', loans:'Займов'}},
    lgd:{fl12:'LGD-12', fl24:'Возмещение мес. 13–24',
         kpi:{fact:fl=>`${fl}: прогноз / факт (тест, взв. EAD)`, bias:b=>`смещение ${b} п. п.`, mae:['MAE, обучение → тест','средняя абсолютная ошибка'],
              sp:['Спирмен (тест)','ранговая связь прогноза и факта'], l24:['Итоговый LGD-24: прогноз / факт (тест)','1 − RR₁₋₁₂ − прогноз'],
              n:['Дефолтов: обучение / тест', e=>`EAD теста ${e} BYN`]},
         charts:{c1:fl=>[`${fl}: прогноз и факт`,'взвешено по EAD, по месяцу дефолта'], c2:['MAE по месяцам','средняя абсолютная ошибка'],
                 c3:['Спирмен по месяцам','считается при n ≥ 20'], c4:['Количество дефолтов','по месяцу дефолта']},
         series:{pred:'Прогноз', fact:'Факт', defaults:'Дефолтов'}},
    band:'тест',
    note:'— тестовый период (out-of-time). Наведите на график, чтобы увидеть значения.',
    table:'Таблица метрик по месяцам', month:'Месяц', sample:'Выборка', total:'Итого', train:'обучение', test:'тест',
    cols:{n_pd:'Займов', n_lgd:'Дефолтов', defaults:'Дефолтов', dr_actual:'Факт DR', pd_pred:'Прогноз PD', calib_ratio:'PD / DR',
          gini:'Gini', ks:'KS', psi:'PSI', ead:'EAD, BYN', fact:'Факт', pred:'Прогноз', bias:'Смещение, п. п.', mae:'MAE',
          spearman:'Спирмен', lgd24_fact:'LGD-24 факт', lgd24_pred:'LGD-24 прогноз'},
    pp:'п. п.',
    foot:T=>`Пороги светофора (внимание / отклонение): падение Gini тест к обучению > ${p0(T.gini_drop[0])} / > ${p0(T.gini_drop[1])}; `+
      `PSI > ${dc(T.psi[0])} / > ${dc(T.psi[1])}; |PD/DR − 1| > ${dc(T.calib[0])} / > ${dc(T.calib[1])}; `+
      `|смещение LGD| > ${T.lgd_bias[0]*100} / > ${T.lgd_bias[1]*100} п. п.; Спирмен < ${dc(T.spearman[0])} / < ${dc(T.spearman[1])}; `+
      `рост MAE тест к обучению > ${p0(T.mae_growth[0])} / > ${p0(T.mae_growth[1])}. Ранговые метрики по месяцам считаются при n ≥ 20.`,
    author:'Автор'
  }
};

let L = I18N.en, lang = 'en', current = 'pd_model', charts = [];
const PREVIEW = new URLSearchParams(location.search).has('preview');
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const dec = s => lang==='ru' ? s.replace('.',',') : s;
const dc = v => dec(String(v));
const p0 = v => dec(String(Math.round(v*1000)/10)) + (lang==='ru' ? ' %' : '%');
const pct = (v,d=1) => v==null ? '—' : dec((v*100).toFixed(d)) + (lang==='ru' ? ' %' : '%');
const num = (v,d=2) => v==null ? '—' : dec(v.toFixed(d));
const int = v => v==null ? '—' : Math.round(v).toLocaleString(L.locale);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

const T = Object.assign({mae_growth:[0.25, 0.5]}, DATA.thresholds);

function worst(lights){
  const vals = Object.values(lights).map(x=>x[1]);
  for (const c of ['red','amber','green','grey']) if (vals.includes(c)) return c;
  return 'grey';
}

const bandPlugin = {
  id:'testband',
  beforeDraw(chart, args, opts){
    const {ctx, chartArea:a, scales:{x}} = chart;
    if (opts.from==null || opts.from<0) return;
    const n = chart.data.labels.length;
    const step = n>1 ? (x.getPixelForValue(1)-x.getPixelForValue(0)) : a.width;
    const left = Math.max(a.left, x.getPixelForValue(opts.from) - step/2);
    ctx.save(); ctx.fillStyle = css('--band'); ctx.fillRect(left, a.top, a.right-left, a.bottom-a.top);
    ctx.fillStyle = css('--muted'); ctx.font = '11px system-ui'; ctx.fillText(L.band, left+6, a.top+12);
    ctx.restore();
  }
};
Chart.register(bandPlugin);
if (PREVIEW) { Chart.defaults.animation = false; document.body.classList.add('preview'); }

function lineChart(el, labels, series, testFrom, fmt, yOpts={}){
  const grid = css('--grid'), txt = css('--text2');
  charts.push(new Chart(el, {
    type:'line',
    data:{labels, datasets: series.map((s,i)=>({label:s.label, data:s.data, borderColor:css(i? '--s2':'--s1'),
      backgroundColor:css(i? '--s2':'--s1'), borderWidth:2, pointRadius:2.5, pointHoverRadius:5, spanGaps:true, tension:.2}))},
    options:{responsive:true, maintainAspectRatio:false, interaction:{mode:'index', intersect:false},
      plugins:{testband:{from:testFrom},
        legend:{display:series.length>1, labels:{color:txt, boxWidth:14, boxHeight:2}},
        tooltip:{callbacks:{label:ctx=>`${ctx.dataset.label}: ${fmt(ctx.parsed.y)}`}}},
      scales:{x:{ticks:{color:txt, maxRotation:0, autoSkip:true, maxTicksLimit:8}, grid:{display:false}},
              y:{ticks:{color:txt, callback:v=>fmt(v)}, grid:{color:grid}, ...yOpts}}}
  }));
}

function barChart(el, labels, data, testFrom, label){
  charts.push(new Chart(el, {type:'bar',
    data:{labels, datasets:[{label, data, backgroundColor:css('--s1'), borderRadius:4, maxBarThickness:18}]},
    options:{responsive:true, maintainAspectRatio:false, plugins:{testband:{from:testFrom}, legend:{display:false},
      tooltip:{callbacks:{label:ctx=>`${label}: ${int(ctx.parsed.y)}`}}},
      scales:{x:{ticks:{color:css('--text2'), maxRotation:0, autoSkip:true, maxTicksLimit:8}, grid:{display:false}},
              y:{ticks:{color:css('--text2')}, grid:{color:css('--grid')}, beginAtZero:true}}}}));
}

const chartCard = (id, [title, note]) =>
  `<div class="card chart"><h3>${title}</h3><p>${note}</p><div class="box"><canvas id="${id}"></canvas></div></div>`;

function fmtLight(key, v){
  if (v==null) return '—';
  if (key==='gini_drop' || key==='mae_growth') return pct(v,0);
  if (key==='lgd_bias') return `${num(v*100,1)} ${L.pp}`;
  return num(v,3);
}

function renderChrome(){
  document.documentElement.lang = lang;
  document.title = L.title;
  document.getElementById('title').textContent = L.title;
  document.getElementById('sub').textContent = L.sub(DATA.generated);
  const src = document.getElementById('src');
  if (LINKS.repo) { src.href = LINKS.repo; src.textContent = `${L.source} ↗`; } else src.remove();
  document.querySelectorAll('.lang button').forEach(b=>b.setAttribute('aria-pressed', b.dataset.lang===lang));
  const tabs = document.getElementById('tabs');
  tabs.innerHTML = '';
  Object.keys(NAMES).forEach(k=>{
    const b = document.createElement('button');
    b.className='tab'; b.setAttribute('role','tab'); b.dataset.k=k;
    const w = worst(DATA.models[k].lights);
    b.innerHTML = `<span class="dot ${LIGHT_CLS[w]}" aria-hidden="true"></span>${NAMES[k]} <span class="status">${L.light[w]}</span>`;
    b.onclick = ()=>show(k);
    tabs.appendChild(b);
  });
  const by = LINKS.author ? `<p>${L.author}: ${LINKS.linkedin ? `<a href="${esc(LINKS.linkedin)}" target="_blank" rel="noopener">${esc(LINKS.author)}</a>` : esc(LINKS.author)}`+
    (LINKS.repo ? ` · <a href="${esc(LINKS.repo)}" target="_blank" rel="noopener">GitHub</a>` : '') + '</p>' : '';
  document.getElementById('foot').innerHTML = `<p>${L.foot(T)}</p>${by}`;
}

function show(k){
  current = k;
  charts.forEach(c=>c.destroy()); charts=[];
  document.querySelectorAll('.tab').forEach(t=>t.setAttribute('aria-selected', t.dataset.k===k));
  try{ localStorage.setItem('mon_tab',k); }catch(e){}
  const m = DATA.models[k], meta = m.meta, ov = m.overall, mon = m.monthly;
  const labels = mon.map(r=>r.month);
  const testFrom = mon.findIndex(r=>r.split==='test');
  const col = f => mon.map(r=>r[f]);

  let kpis, cards, table, nKey;
  if (m.kind==='pd'){
    const K = L.pd.kpi;
    kpis = [
      [K[0][0], `${num(ov.train.gini)} → ${num(ov.test.gini)}`, K[0][1]({ks:num(ov.test.ks)})],
      [K[1][0], `${pct(ov.test.pd_pred)} / ${pct(ov.test.dr_actual)}`, K[1][1]({ratio:num(ov.test.calib_ratio)})],
      [K[2][0], num(ov.test.psi,3), K[2][1]],
      [K[3][0], `${int(ov.train.n)} / ${int(ov.test.n)}`, K[3][1]({d:`${int(ov.train.defaults)} / ${int(ov.test.defaults)}`})]];
    cards = L.pd.charts.map((c,i)=>chartCard('c'+(i+1), c)).join('');
    table = ['n','defaults','dr_actual','pd_pred','calib_ratio','gini','ks','psi']; nKey = 'n_pd';
  } else {
    const is24 = m.kind==='lgd24', fl = is24 ? L.lgd.fl24 : L.lgd.fl12, K = L.lgd.kpi, C = L.lgd.charts;
    kpis = [
      [K.fact(fl), `${pct(ov.test.pred)} / ${pct(ov.test.fact)}`, K.bias(num(ov.test.bias*100,1))],
      [K.mae[0], `${num(ov.train.mae,3)} → ${num(ov.test.mae,3)}`, K.mae[1]],
      [K.sp[0], num(ov.test.spearman), K.sp[1]],
      is24 ? [K.l24[0], `${pct(ov.test.lgd24_pred)} / ${pct(ov.test.lgd24_fact)}`, K.l24[1]]
           : [K.n[0], `${int(ov.train.n)} / ${int(ov.test.n)}`, K.n[1](int(ov.test.ead))]];
    cards = chartCard('c1', C.c1(fl)) + chartCard('c2', C.c2) + chartCard('c3', C.c3) + chartCard('c4', C.c4);
    table = is24 ? ['n','ead','fact','pred','bias','mae','spearman','lgd24_fact','lgd24_pred'] : ['n','ead','fact','pred','bias','mae','spearman'];
    nKey = 'n_lgd';
  }

  const lights = Object.entries(m.lights).map(([key,[v,c]])=>
    `<div class="card light"><span class="dot ${LIGHT_CLS[c]}" aria-hidden="true"></span><div>
      <div class="t">${L.lights[key] || esc(key)}</div><div class="v">${fmtLight(key, v)} · ${L.light[c]}</div></div></div>`).join('');

  const fmtCell = (f,v) => v==null ? '—' : (['n','defaults','ead'].includes(f) ? int(v) :
      ['dr_actual','pd_pred','fact','pred','lgd24_fact','lgd24_pred'].includes(f) ? pct(v) : f==='bias' ? num(v*100,1) : num(v,3));
  const head = f => f==='n' ? L.cols[nKey] : L.cols[f];
  const thead = `<tr><th>${L.month}</th><th>${L.sample}</th>${table.map(f=>`<th>${head(f)}</th>`).join('')}</tr>`;
  const ovrows = ['train','test'].map(s=>`<tr><td><b>${L.total}</b></td><td>${L[s]}</td>${table.map(f=>`<td>${fmtCell(f,ov[s][f])}</td>`).join('')}</tr>`).join('');
  const rows = mon.map(r=>`<tr><td>${r.month}</td><td>${L[r.split]}</td>${table.map(f=>`<td>${fmtCell(f,r[f])}</td>`).join('')}</tr>`).join('');
  const algo = meta.algorithm ? (L.algo[meta.algorithm] || esc(meta.algorithm)) : '—';
  const run = meta.run_url ? `<a href="${esc(meta.run_url)}" target="_blank" rel="noopener">${esc(meta.run_name)}</a>` : esc(meta.run_name);
  const M = L.meta;

  document.getElementById('panel').innerHTML = `
    <div class="card meta-card"><p style="margin:0 0 12px;color:var(--text2)">${L.desc[k]}</p>
      <div class="meta">
        <div>${M[0]}<b>${esc(meta.name)}</b></div><div>${M[1]}<b>${esc(meta.version)}</b></div>
        <div>${M[2]}<b>${algo}</b></div><div>${M[3]}<b>${esc(meta.registered)}</b></div>
        <div>${M[4]}<b>${run}</b></div><div>${M[5]}<b>${meta.oot_split ? esc(L.split(meta.oot_split)) : '—'}</b></div>
      </div></div>
    <div class="kpis">${kpis.map(([l,v,s])=>`<div class="card kpi"><div class="lab">${l}</div><div class="val">${v}</div><div class="sub">${s}</div></div>`).join('')}</div>
    <div class="lights">${lights}</div>
    <p class="legend-note"><span class="band"></span> ${L.note}</p>
    <div class="grid">${cards}</div>
    <details><summary>${L.table}</summary><div class="card tablewrap" style="margin-top:8px"><table>${thead}${ovrows}${rows}</table></div></details>`;

  if (m.kind==='pd'){
    const S = L.pd.series;
    lineChart('c1', labels, [{label:S.pd, data:col('pd_pred')}, {label:S.dr, data:col('dr_actual')}], testFrom, v=>pct(v), {beginAtZero:true});
    lineChart('c2', labels, [{label:'Gini', data:col('gini')}], testFrom, v=>num(v));
    lineChart('c3', labels, [{label:'PSI', data:col('psi')}], testFrom, v=>num(v,3), {beginAtZero:true});
    barChart('c4', labels, col('n'), testFrom, S.loans);
  } else {
    const S = L.lgd.series;
    lineChart('c1', labels, [{label:S.pred, data:col('pred')}, {label:S.fact, data:col('fact')}], testFrom, v=>pct(v), {min:0, max:1});
    lineChart('c2', labels, [{label:'MAE', data:col('mae')}], testFrom, v=>num(v,3), {beginAtZero:true});
    lineChart('c3', labels, [{label:L.cols.spearman, data:col('spearman')}], testFrom, v=>num(v));
    barChart('c4', labels, col('n'), testFrom, S.defaults);
  }
}

function setLang(l, remember){
  lang = I18N[l] ? l : 'en'; L = I18N[lang];
  if (remember) { try{ localStorage.setItem('mon_lang', lang); }catch(e){} }
  renderChrome(); show(current);
}

document.querySelectorAll('.lang button').forEach(b=>b.onclick = ()=>setLang(b.dataset.lang, true));

const qs = new URLSearchParams(location.search);
let start = 'pd_model', startLang = qs.get('lang');
try{
  const s = localStorage.getItem('mon_tab'); if (!PREVIEW && s && DATA.models[s]) start = s;
  if (!startLang) startLang = localStorage.getItem('mon_lang');
}catch(e){}
if (!startLang) startLang = (navigator.language || '').toLowerCase().startsWith('ru') ? 'ru' : 'en';
current = start;
setLang(startLang, false);
window.__dashboardReady = true;
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', ()=>show(current));
</script>
</body>
</html>
"""

DESCRIPTION = ("Monitoring of PD and LGD models loaded from MLflow Model Registry: monthly Gini, KS, PSI and "
               "calibration on train and out-of-time samples, with traffic-light alerts. Synthetic data.")


def build_dashboard(payload, path, site_url=''):
    """Write the dashboard to ``path``. ``site_url`` is the public URL of the page (ends with '/')."""
    links = payload.get('links', {})
    page = (TEMPLATE
            .replace('__DESCRIPTION__', html.escape(DESCRIPTION))
            .replace('__AUTHOR__', html.escape(links.get('author', '')))
            .replace('__SITE_URL__', html.escape(site_url))
            .replace('__DATA__', json.dumps(payload, ensure_ascii=False).replace('</', '<\\/')))
    Path(path).write_text(page, encoding='utf8')
