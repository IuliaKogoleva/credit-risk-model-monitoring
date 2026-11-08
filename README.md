# Credit risk model monitoring: PD, LGD-12, LGD-24

Monitoring of credit risk models registered in **MLflow on DagsHub**. The script loads the latest model versions from the MLflow Model Registry, recalculates quality metrics on the train and out-of-time test samples — overall and **by month** — applies traffic-light thresholds and builds an interactive **HTML dashboard**, published to **GitHub Pages** by GitHub Actions.

Companion project to [credit-risk-models](https://github.com/IuliaKogoleva/credit-risk-models), where the models are trained on a synthetic consumer loan portfolio.

> **All data are synthetic** and do not relate to any real bank or borrower.

*Краткое описание на русском — в конце файла.*

---

## How it works

```
credit-risk-models (training)            credit-risk-model-monitoring (this repo)
─────────────────────────────            ─────────────────────────────────────────
train PD / LGD-12 / LGD-24  ──► MLflow Model Registry on DagsHub ──► load latest versions
                                                                      │
portfolio data (GitHub) ─────────────────────────────────────────────► rebuild samples
                                                                      │
                                                     metrics overall + by month, traffic lights
                                                                      │
                                              docs/index.html ──► GitHub Pages (dashboard)
                                              metrics CSV/JSON ──► (optional) MLflow run "model-monitoring"
```

## Metrics

| Model | Monthly dimension | Metrics | Traffic lights |
|---|---|---|---|
| **PD** | issue month | number of loans and defaults, predicted PD vs observed default rate, calibration ratio, Gini, KS, PSI of the score vs train | Gini drop test vs train; PSI; \|PD/DR − 1\| |
| **LGD-12** | default month | number of defaults, EAD, predicted vs actual LGD (EAD-weighted), bias, MAE, Spearman | \|bias\|; Spearman; MAE growth test vs train |
| **LGD-24** | default month | same as LGD-12 for recovery months 13–24, plus final LGD-24 = 1 − RR₁₋₁₂ − forecast | same as LGD-12 |

Default thresholds (warning / alert): Gini drop > 10% / 20%; PSI > 0.10 / 0.25; \|PD/DR − 1\| > 0.20 / 0.35; \|LGD bias\| > 5 / 10 pp; Spearman < 0.30 / 0.15; MAE growth > 25% / 50%. Rank metrics by month are calculated when a month has at least 20 observations. Thresholds are set in `TH` in `src/monitoring.py`.

## Dashboard

One tab per model with a status indicator. Each tab shows model metadata (version, algorithm, registration date, link to the MLflow run), headline metrics for train and test, traffic lights, four monthly charts with the out-of-time period shaded, and a full monthly metrics table. Light and dark themes, works on mobile.

After the first workflow run the dashboard is available at
`https://iuliakogoleva.github.io/credit-risk-model-monitoring/`.

## Repository structure

```
credit-risk-model-monitoring/
├── src/
│   ├── monitoring.py     # load models from MLflow, compute metrics, build report
│   ├── features.py       # data preparation (same logic as in credit-risk-models)
│   └── dashboard.py      # HTML dashboard (Chart.js)
├── docs/                 # generated report (index.html, metrics CSV/JSON)
├── .github/workflows/monitoring.yml
├── requirements.txt
└── README.md
```

## Run in GitHub Actions (recommended)

1. **Secrets:** Settings → Secrets and variables → Actions → add `DAGSHUB_USER`, `DAGSHUB_REPO` (`credit-risk-models` — the DagsHub repository where the models are registered) and `DAGSHUB_TOKEN`.
2. **GitHub Pages:** Settings → Pages → *Build and deployment* → Source: **GitHub Actions**.
3. **Run:** Actions → *model-monitoring* → **Run workflow**. The workflow also runs automatically on the 1st of every month.

The report is published to GitHub Pages and saved as the `monitoring-report` artifact of the run.

## Run locally

```bash
pip install -r requirements.txt
export DAGSHUB_USER=<dagshub_login>
export DAGSHUB_REPO=credit-risk-models
export DAGSHUB_TOKEN=<token>          # never put the token in code

python src/monitoring.py                         # data are read from the credit-risk-models repo on GitHub
python src/monitoring.py --data path/to/consumer_loans_portfolio.xlsx
python src/monitoring.py --version pd_model=1    # a specific model version
python src/monitoring.py --log-to-mlflow         # also log the report to MLflow (experiment "model-monitoring")
python src/monitoring.py --local-mlflow ../credit-risk-models/mlruns   # local MLflow instead of DagsHub
```

Open `docs/index.html` in a browser.

## Notes

- Data preparation in `src/features.py` repeats the logic of `credit-risk-models/src/credit_models.py`; if targets, features or the out-of-time split change there, update this file too.
- Recent MLflow versions save scikit-learn models with *skops* and require a list of trusted types on load; the script adds the types reported by MLflow automatically.
- On the synthetic portfolio the LGD-24 gradient boosting model shows strong overfitting (MAE on test about twice the train value), which the dashboard flags in red — a real monitoring finding rather than a bug.

---

## Кратко на русском

Мониторинг моделей PD, LGD-12 и LGD-24 из проекта [credit-risk-models](https://github.com/IuliaKogoleva/credit-risk-models). Скрипт загружает последние версии моделей из MLflow Model Registry на DagsHub и считает показатели качества на обучающей и тестовой выборках, в целом и по месяцам: PD — по месяцу выдачи, LGD — по месяцу дефолта. Затем выставляет «светофор» по порогам и строит HTML-дашборд. GitHub Actions запускает мониторинг вручную или раз в месяц и публикует дашборд на GitHub Pages. Данные полностью синтетические.

## Author

Iulia Kogoleva — [github.com/IuliaKogoleva](https://github.com/IuliaKogoleva)
