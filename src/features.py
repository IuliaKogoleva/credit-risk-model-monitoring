"""
Подготовка данных для мониторинга моделей PD, LGD-12, LGD-24.
Логика совпадает с проектом credit-risk-models (src/credit_models.py): те же целевые
переменные, признаки и out-of-time разбиение. При изменении логики в исходном проекте
обновите и этот файл.
"""
import os
import numpy as np, pandas as pd

REPORT = pd.Period('2026-10', 'M')
APP_NUM = ['amount_or_limit', 'term_months', 'interest_rate', 'age', 'dependants', 'work_experience_months',
           'monthly_income', 'salary_client', 'credit_history_months', 'active_loans_cnt', 'other_loans_payment', 'pti']
APP_CAT = ['product', 'channel', 'sex', 'region', 'education', 'marital_status', 'employment', 'client_type', 'max_dpd_hist_12m']


# ------------------------------------------------------------------ data
def load(path):
    if path.endswith('.xlsx'):
        print('Читаю Excel (1–2 минуты)...')
        sh = pd.read_excel(path, sheet_name=['Займы', 'Помесячно', 'Взыскание'])
        L, M, C = sh['Займы'], sh['Помесячно'], sh['Взыскание']
    else:                                     # папка с loans.csv / monthly.csv / collection.csv
        L = pd.read_csv(os.path.join(path, 'loans.csv'))
        M = pd.read_csv(os.path.join(path, 'monthly.csv'))
        C = pd.read_csv(os.path.join(path, 'collection.csv'))
    L['term_months'] = L['term_months'].fillna(0)        # карта — без срока
    L['issue_month'] = L['issue_month'].astype(str)
    return L, M, C


def months_between(a, b):
    return (pd.Period(b, 'M') - pd.Period(a, 'M')).n


def build_pd(L):
    df = L.copy()
    df['target'] = df['default_9m'].astype(int)
    df['split'] = np.where(df['issue_month'] <= '2024-06', 'train', 'test')     # out-of-time
    return df


def pre_default_features(L, M):
    """Поведение займа до дефолта по помесячной таблице."""
    d = L[L['default_any'] == 1][['loan_id', 'default_mob']]
    m = M.merge(d, on='loan_id')
    m = m[m['mob'] <= m['default_mob']]
    g = m.groupby('loan_id').agg(
        months_before_default=('mob', 'max'),
        paid_before_default=('paid_total', 'sum'),
        sched_before_default=('scheduled_payment', 'sum'),
        months_with_payment=('paid_total', lambda x: int((x > 0).sum())),
        months_dpd_pos=('max_dpd_in_month', lambda x: int((x > 0).sum())))
    g['paid_to_sched'] = g['paid_before_default'] / g['sched_before_default'].replace(0, np.nan)
    return g.reset_index()


def build_lgd(L, M, C):
    d = L[L['default_any'] == 1].copy()
    d['obs_months'] = d['default_month'].astype(str).map(lambda x: months_between(x, str(REPORT)))
    d = d.merge(pre_default_features(L, M), on='loan_id', how='left')
    d['log_ead'] = np.log1p(d['ead'])
    d['ead_to_amount'] = d['ead'] / d['amount_or_limit']
    d['ead_to_income'] = d['ead'] / d['monthly_income']
    c = C.copy()
    c['net'] = c['collected'] - c['legal_fee'] - c['postage_fee']
    c = c.merge(d[['loan_id', 'ead']], on='loan_id')

    def window(a, b, col='net'):
        x = c[(c['months_since_default'] >= a) & (c['months_since_default'] <= b)]
        return x.groupby('loan_id')[col].sum()

    d['rr_0_12'] = d['loan_id'].map(window(1, 12)).fillna(0) / d['ead']
    d['rr_13_24'] = d['loan_id'].map(window(13, 24)).fillna(0) / d['ead']

    # признаки первого года взыскания (для LGD-24)
    y1 = c[c['months_since_default'] <= 12]
    f = y1.groupby('loan_id').agg(
        calls_12=('calls_cnt', 'sum'), sms_12=('sms_cnt', 'sum'), rpc_12=('right_party_contacts', 'sum'),
        promises_12=('promises_cnt', 'sum'), promises_sum_12=('promises_sum', 'sum'),
        pay_months_12=('collected', lambda x: int((x > 0).sum())),
        legal_cost_12=('legal_fee', 'sum'))
    last3 = y1[y1['months_since_default'] >= 10].groupby('loan_id')['collected'].sum().rename('collected_m10_12')
    garn = y1[y1['legal_stage'].astype(str).str.contains('удержания')].groupby('loan_id').size().rename('garnish_months_12')
    debt12 = y1[y1['months_since_default'] == 12].set_index('loan_id')['debt_end'].rename('debt_12')
    d = d.merge(f, on='loan_id', how='left').merge(last3, on='loan_id', how='left') \
         .merge(garn, on='loan_id', how='left').merge(debt12, on='loan_id', how='left')
    for col in ['collected_m10_12', 'garnish_months_12']:
        d[col] = d[col].fillna(0)
    d['debt12_to_ead'] = d['debt_12'] / d['ead']
    d['collected_m10_12_share'] = d['collected_m10_12'] / d['ead']
    lgd12 = d[d['obs_months'] >= 12].copy()
    lgd12['target'] = (1 - lgd12['rr_0_12']).clip(0, 1)
    # для LGD-24 нужны займы, не погашенные к 12 месяцу (иначе прогнозировать нечего)
    lgd24 = d[(d['obs_months'] >= 24) & (d['debt_12'].fillna(0) > 1)].copy()
    lgd24['target'] = lgd24['rr_13_24'].clip(0, 1)          # модель прогнозирует возмещение мес. 13–24
    for df in (lgd12, lgd24):                                # out-of-time: ранние 70 % дефолтов — обучение
        cut = df['default_month'].astype(str).sort_values().iloc[int(len(df) * 0.7)]
        df['split'] = np.where(df['default_month'].astype(str) < cut, 'train', 'test')
        df.attrs['oot_cut'] = cut
    return lgd12, lgd24


def lgd_features(kind):
    base_num = ['ead', 'log_ead', 'ead_to_amount', 'ead_to_income', 'default_mob', 'months_with_payment',
                'months_dpd_pos', 'paid_to_sched', 'interest_rate', 'age', 'monthly_income', 'work_experience_months',
                'salary_client', 'active_loans_cnt', 'pti']
    base_cat = ['product', 'channel', 'employment', 'region', 'education']
    if kind == 'lgd24':
        base_num = base_num + ['rr_0_12', 'debt12_to_ead', 'collected_m10_12_share', 'pay_months_12', 'garnish_months_12',
                               'calls_12', 'sms_12', 'rpc_12', 'promises_12', 'promises_sum_12', 'legal_cost_12']
    return base_num, base_cat


