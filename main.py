import logging
import os
import settings
import data_manager
from policy_learner import PolicyLearner
from market_manager import SmMarketManager
import pandas as pd
import numpy as np

if __name__ == '__main__':
    stock_code = '005930'  # 삼성전자

    market_mgr = SmMarketManager()
    market_mgr.read_symbol_from_file()

    # 로그 기록
    log_dir = os.path.join(settings.BASE_DIR, 'logs/%s' % stock_code)
    timestr = settings.get_time_str()
    if not os.path.exists('logs/%s' % stock_code):
        os.makedirs('logs/%s' % stock_code)
    file_handler = logging.FileHandler(filename=os.path.join(
        log_dir, "%s_%s.log" % (stock_code, timestr)), encoding='utf-8')
    stream_handler = logging.StreamHandler()
    file_handler.setLevel(logging.DEBUG)
    stream_handler.setLevel(logging.INFO)
    logging.basicConfig(format="%(message)s",
                        handlers=[file_handler, stream_handler], level=logging.DEBUG)

    excel_file = os.path.join(settings.BASE_DIR, 'data/chart_data/future10y.xlsx')
    logging.debug('학습 시작')
    xlsx = pd.ExcelFile(excel_file)
    movies_sheets = []
    for sheet in xlsx.sheet_names:
        movies_sheets.append(xlsx.parse(sheet))

    symbol = movies_sheets[10]
    print(symbol)
    if 'volume' in symbol:
        symbol['volume'] = symbol['volume'].replace('-', np.nan)
        symbol['volume'] = symbol['volume'].replace(r'[KM]+$', '', regex=True).astype(float) * \
            symbol['volume'].astype(str).str.extract(r'[\d\.]+([KM]+)', expand=False).fillna(1)\
            .replace(['K', 'M'], [10 ** 3, 10 ** 6]).astype(int)
        symbol['volume'].fillna(method='ffill', inplace=True)
        symbol['volume'].fillna(method='bfill', inplace=True)

        # 주식 데이터 준비
    chart_data = data_manager.load_chart_data(
        os.path.join(settings.BASE_DIR, 'data/chart_data/wti.csv'))
    prep_data = data_manager.preprocess(chart_data)
    training_data = data_manager.build_training_data(prep_data)

    # 기간 필터링
    training_data = training_data[(training_data['date'] >= '2017-01-01') &
                                  (training_data['date'] <= '2017-12-31')]
    training_data = training_data.dropna()

    # 차트 데이터 분리
    features_chart_data = ['date', 'open', 'high', 'low', 'close', 'volume']
    chart_data = training_data[features_chart_data]

    # 학습 데이터 분리
    features_training_data = [
        'open_lastclose_ratio', 'high_close_ratio', 'low_close_ratio',
        'close_lastclose_ratio', 'volume_lastvolume_ratio',
        'close_ma5_ratio', 'volume_ma5_ratio',
        'close_ma10_ratio', 'volume_ma10_ratio',
        'close_ma20_ratio', 'volume_ma20_ratio',
        'close_ma60_ratio', 'volume_ma60_ratio',
        'close_ma120_ratio', 'volume_ma120_ratio'
    ]
    # 학습데이터 분리
    training_data = training_data[features_training_data]

    # 강화학습 시작
    policy_learner = PolicyLearner(
        stock_code=stock_code, chart_data=chart_data, training_data=training_data,
        min_trading_unit=1, max_trading_unit=2, delayed_reward_threshold=.2, lr=.001)
    policy_learner.fit(balance=10000000, num_epoches=1000,
                       discount_factor=0, start_epsilon=.5)

    # 정책 신경망을 파일로 저장
    model_dir = os.path.join(settings.BASE_DIR, 'models/%s' % stock_code)
    if not os.path.isdir(model_dir):
        os.makedirs(model_dir)
    model_path = os.path.join(model_dir, 'model_%s.h5' % timestr)
    policy_learner.policy_network.save_model(model_path)
