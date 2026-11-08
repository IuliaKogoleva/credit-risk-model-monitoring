"""
Мониторинг моделей PD, LGD-12 и LGD-24, зарегистрированных в MLflow (DagsHub).

Скрипт:
  1) загружает последние (или заданные) версии моделей из MLflow Model Registry;
  2) готовит данные условного портфеля так же, как при обучении;
  3) считает показатели качества на обучающей и тестовой выборках — в целом и по месяцам
     (PD — по месяцу выдачи, LGD — по месяцу дефолта);
  4) выставляет «светофор» по порогам и строит HTML-дашборд docs/index.html (EN/RU);
  5) по желанию логирует результаты мониторинга в MLflow.

Запуск:
  pip install -r requirements.txt
  export DAGSHUB_USER=<логин> DAGSHUB_REPO=credit-risk-models DAGSHUB_TOKEN=<токен>
  python src/monitoring.py                    # данные — из репозитория credit-risk-models на GitHub
  python src/monitoring.py --data path/to/consumer_loans_portfolio.xlsx
  python src/monitoring.py --log-to-mlflow    # дополнительно залогировать отчёт в MLflow
"""
import argparse, inspect, json, os, re, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score, mean_absolute_error
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import features as F
from dashboard import build_dashboard

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = 'https://github.com/IuliaKogoleva/credit-risk-models/raw/main/data/consumer_loans_portfolio.xlsx'
MODELS = ['pd_model', 'lgd12_model', 'lgd24_model']
MIN_N = 20                     # минимум наблюдений в месяце для ранговых метрик
AUTHOR = 'Iulia Kogoleva'
LINKEDIN = 'https://www.linkedin.com/in/iulia-kogoleva'
DEFAULT_REPO = 'IuliaKogoleva/credit-risk-model-monitoring'

# пороги светофора
TH = {
    'gini_drop':  (0.10, 0.20),   # относительное падение Gini теста к обучению
    'psi':        (0.10, 0.25),
    'calib':      (0.20, 0.35),   # |прогноз/факт − 1| для PD
    'lgd_bias':   (0.05, 0.10),   # |смещение| прогноза LGD, доли
    'spearman':   (0.30, 0.15),   # чем меньше, тем хуже: <0.30 жёлтый, <0.15 красный
    'mae_growth': (0.25, 0.50),   # относительный рост MAE теста к обучению (LGD)
}


# ------------------------------------------------------------------ metrics
def gini(y, p):
    return float(2 * roc_auc_score(y, p) - 1) if len(set(y)) == 2 else np.nan


def ks(y, p):
    if len(set(y)) < 2:
        return np.nan
    df = pd.DataFrame({'y': y, 'p': p}).sort_values('p')
    cg = (1 - df['y']).cumsum() / (1 - df['y']).sum()
    cb = df['y'].cumsum() / df['y'].sum()
    return float((cg - cb).abs().max())


def psi(base, cur, bins=10):
    if len(cur) == 0:
        return np.nan
    q = np.unique(np.quantile(base, np.linspace(0, 1, bins + 1)))
    if len(q) < 3:
        return np.nan
    eb = np.histogram(base, q)[0] / len(base) + 1e-6
    ec = np.histogram(np.clip(cur, q[0], q[-1]), q)[0] / len(cur) + 1e-6
    return float(np.sum((eb - ec) * np.log(eb / ec)))


def light(value, warn, alert, higher_is_worse=True):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return 'grey'
    if higher_is_worse:
        return 'red' if value > alert else 'amber' if value > warn else 'green'
    return 'red' if value < alert else 'amber' if value < warn else 'green'


def pd_metrics(df, p, base_scores):
    y = df['target'].values
    return {'n': int(len(df)), 'defaults': int(y.sum()), 'dr_actual': float(y.mean()), 'pd_pred': float(p.mean()),
            'calib_ratio': float(p.mean() / y.mean()) if y.mean() > 0 else np.nan,
            'gini': gini(y, p) if len(df) >= MIN_N else np.nan, 'ks': ks(y, p) if len(df) >= MIN_N else np.nan,
            'psi': psi(base_scores, p)}


def lgd_metrics(df, p, kind):
    y, w = df['target'].values, df['ead'].values
    m = {'n': int(len(df)), 'ead': float(w.sum()),
         'fact': float(np.average(y, weights=w)), 'pred': float(np.average(p, weights=w)),
         'mae': float(mean_absolute_error(y, p)),
         'spearman': float(spearmanr(y, p).correlation) if len(df) >= MIN_N and np.std(y) > 0 else np.nan}
    m['bias'] = m['pred'] - m['fact']
    if kind == 'lgd24':                                  # итоговый LGD-24 = 1 − RR12 факт − прогноз 13–24
        f24 = (1 - df['rr_0_12'] - df['target']).clip(0, 1); p24 = (1 - df['rr_0_12'] - p).clip(0, 1)
        m['lgd24_fact'] = float(np.average(f24, weights=w)); m['lgd24_pred'] = float(np.average(p24, weights=w))
    return m


# ------------------------------------------------------------------ mlflow
def connect_mlflow(local):
    import mlflow
    if local:
        mlflow.set_tracking_uri((Path(local).resolve()).as_uri())
        return mlflow, None
    user, repo, token = (os.environ.get(k) for k in ('DAGSHUB_USER', 'DAGSHUB_REPO', 'DAGSHUB_TOKEN'))
    if not (user and repo and token):
        raise SystemExit('Задайте переменные окружения DAGSHUB_USER, DAGSHUB_REPO, DAGSHUB_TOKEN.')
    os.environ['MLFLOW_TRACKING_USERNAME'] = user
    os.environ['MLFLOW_TRACKING_PASSWORD'] = token
    uri = f'https://dagshub.com/{user}/{repo}.mlflow'
    mlflow.set_tracking_uri(uri)
    return mlflow, uri


def load_sklearn(mlflow, uri):
    """Загрузка sklearn-модели; новые версии MLflow (skops) требуют список доверенных типов."""
    from mlflow.exceptions import MlflowException
    supports = 'skops_trusted_types' in inspect.signature(mlflow.sklearn.load_model).parameters
    trusted = ['numpy.dtype']
    for _ in range(6):
        try:
            return mlflow.sklearn.load_model(uri, **({'skops_trusted_types': trusted} if supports else {}))
        except MlflowException as e:
            found = re.search(r'Untrusted types found in the file: \[(.*?)\]', str(e))
            if not (supports and found):
                raise
            trusted = sorted(set(trusted) | {t.strip(" '\"") for t in found.group(1).split(',')})
    raise RuntimeError(f'Не удалось загрузить {uri}')


def load_models(mlflow, tracking_uri, versions):
    from mlflow import MlflowClient
    client = MlflowClient()
    out = {}
    for name in MODELS:
        mv = client.search_model_versions(f"name='{name}'")
        if not mv:
            raise SystemExit(f'В реестре нет модели {name}. Сначала запустите обучение в credit-risk-models.')
        v = versions.get(name) or str(max(int(x.version) for x in mv))
        info = next(x for x in mv if str(x.version) == str(v))
        model = load_sklearn(mlflow, f'models:/{name}/{v}')
        run = client.get_run(info.run_id)
        out[name] = dict(model=model, meta={
            'name': name, 'version': str(v), 'run_id': info.run_id, 'run_name': run.info.run_name,
            'registered': datetime.fromtimestamp(int(info.creation_timestamp) / 1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
            'algorithm': run.data.params.get('algorithm', ''), 'oot_split': run.data.params.get('oot_split', ''),
            'run_url': (f"{tracking_uri}/#/experiments/{run.info.experiment_id}/runs/{info.run_id}" if tracking_uri else '')})
        print(f'Загружена {name} v{v} ({out[name]["meta"]["algorithm"]})')
    return out


# ------------------------------------------------------------------ evaluation
def model_features(model, fallback):
    """Список признаков берём из самой модели (ColumnTransformer), иначе — из features.py."""
    try:
        cols = list(model.feature_names_in_)
        if cols:
            return cols
    except AttributeError:
        pass
    return fallback


def evaluate(models, L, M, C):
    res = {}
    # ---- PD
    m = models['pd_model']['model']
    df = F.build_pd(L)
    cols = model_features(m, F.APP_NUM + F.APP_CAT)
    df['p'] = m.predict_proba(df[cols])[:, 1]
    df['month'] = df['issue_month'].astype(str)
    base = df.loc[df.split == 'train', 'p'].values
    overall = {s: pd_metrics(g, g['p'].values, base) for s, g in df.groupby('split')}
    monthly = [{'month': mo, 'split': g['split'].iloc[0], **pd_metrics(g, g['p'].values, base)} for mo, g in df.groupby('month')]
    tr, te = overall['train'], overall['test']
    drop = (tr['gini'] - te['gini']) / tr['gini'] if tr['gini'] else np.nan
    # ключи светофоров стабильны; подписи на EN/RU задаются в dashboard.py
    res['pd_model'] = dict(kind='pd', overall=overall, monthly=monthly, lights={
        'gini_drop': (drop, light(drop, *TH['gini_drop'])),
        'psi': (te['psi'], light(te['psi'], *TH['psi'])),
        'calib': (abs(te['calib_ratio'] - 1), light(abs(te['calib_ratio'] - 1), *TH['calib']))})

    # ---- LGD
    lgd12, lgd24 = F.build_lgd(L, M, C)
    for name, kind, d in [('lgd12_model', 'lgd12', lgd12), ('lgd24_model', 'lgd24', lgd24)]:
        m = models[name]['model']
        num, cat = F.lgd_features(kind)
        cols = model_features(m, num + cat)
        d = d.copy()
        d['p'] = np.clip(m.predict(d[cols]), 0, 1)
        d['month'] = d['default_month'].astype(str)
        overall = {s: lgd_metrics(g, g['p'].values, kind) for s, g in d.groupby('split')}
        monthly = [{'month': mo, 'split': g['split'].iloc[0], **lgd_metrics(g, g['p'].values, kind)} for mo, g in d.groupby('month')]
        te = overall['test']
        growth = (te['mae'] - overall['train']['mae']) / overall['train']['mae']
        res[name] = dict(kind=kind, overall=overall, monthly=monthly, lights={
            'lgd_bias': (abs(te['bias']), light(abs(te['bias']), *TH['lgd_bias'])),
            'spearman': (te['spearman'], light(te['spearman'], *TH['spearman'], higher_is_worse=False)),
            'mae_growth': (growth, light(growth, *TH['mae_growth']))})
    return res


def to_frames(res):
    rows = []
    for name, r in res.items():
        for x in r['monthly']:
            rows.append({'model': name, **x})
    monthly = pd.DataFrame(rows)
    ov = pd.DataFrame([{'model': n, 'split': s, **v} for n, r in res.items() for s, v in r['overall'].items()])
    return monthly, ov


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if np.isnan(o) else round(float(o), 6)
    if isinstance(o, np.integer):
        return int(o)
    return o


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=DEFAULT_DATA, help='Excel портфеля: путь или URL')
    ap.add_argument('--local-mlflow', default=None, help='путь к локальной папке mlruns вместо DagsHub')
    ap.add_argument('--version', action='append', default=[], help='конкретная версия, например pd_model=2')
    ap.add_argument('--log-to-mlflow', action='store_true', help='залогировать отчёт в эксперимент model-monitoring')
    ap.add_argument('--out', default=str(ROOT / 'docs'))
    ap.add_argument('--site-url', default=None, help='публичный адрес дашборда (для превью ссылок); '
                    'по умолчанию — GitHub Pages репозитория')
    a = ap.parse_args()
    repo = os.environ.get('GITHUB_REPOSITORY', DEFAULT_REPO)
    owner, name = repo.split('/', 1)
    site_url = a.site_url or f'https://{owner.lower()}.github.io/{name}/'
    if not site_url.endswith('/'):
        site_url += '/'

    mlflow, uri = connect_mlflow(a.local_mlflow)
    versions = dict(v.split('=') for v in a.version)
    models = load_models(mlflow, uri, versions)
    L, M, C = F.load(a.data)
    res = evaluate(models, L, M, C)

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    monthly, overall = to_frames(res)
    monthly.to_csv(out / 'metrics_monthly.csv', index=False)
    overall.to_csv(out / 'metrics_overall.csv', index=False)
    payload = clean({'generated': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'), 'data_source': a.data,
                     'thresholds': TH, 'links': {'author': AUTHOR, 'linkedin': LINKEDIN, 'repo': f'https://github.com/{repo}'},
                     'models': {n: {**res[n], 'meta': models[n]['meta']} for n in MODELS}})
    (out / 'metrics.json').write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding='utf8')
    build_dashboard(payload, out / 'index.html', site_url=site_url)
    print('Дашборд:', out / 'index.html')

    if a.log_to_mlflow:
        mlflow.set_experiment('model-monitoring')
        with mlflow.start_run(run_name=f"monitoring-{datetime.now():%Y-%m-%d}"):
            mlflow.log_params({f'{n}_version': models[n]['meta']['version'] for n in MODELS})
            for n, r in res.items():
                for s, v in r['overall'].items():
                    mlflow.log_metrics({f'{n}__{s}__{k}': float(x) for k, x in v.items()
                                        if isinstance(x, (int, float)) and not np.isnan(x)})
            for f in ['index.html', 'metrics_monthly.csv', 'metrics_overall.csv', 'metrics.json']:
                mlflow.log_artifact(str(out / f))
        print('Отчёт залогирован в эксперимент model-monitoring')


if __name__ == '__main__':
    main()
