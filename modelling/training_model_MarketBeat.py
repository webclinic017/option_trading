# Load packages
import pandas as pd
import numpy as np
import os
os.chdir('/home/pi/Documents/python_scripts/option_trading')
from sklearn.model_selection import train_test_split, GroupShuffleSplit
from sklearn.metrics import auc, roc_curve
from datetime import datetime, timedelta
from option_trading_nonprod.models.tree_based import *
from option_trading_nonprod.models.calibrate import *
from option_trading_nonprod.process.stock_price_enriching import *



#######################
# Load and prepare data
df_all = pd.read_csv('data/marketbeat_yf_enr_1.csv')

# Set target
df_all['baseLastPrice'] = df_all['firstPrice']
df_all['strikePrice'] = 1.1 * df_all['baseLastPrice']
df_all['reachedStrikePrice'] = np.where(df_all['maxPrice'] >= df_all['strikePrice'],1,0)

# filter set on applicable rows
df = df_all.reset_index(drop=True)

# custom added variables
df['indicatorPresent'] = np.where(df['indicators'].isnull(),0,1)
df['upcomingEarning'] = np.where(df['indicators'].str.contains('Upcoming Earnings', na=False),1,0)
df['earningAnnounced'] = np.where(df['indicators'].str.contains('Earnings Announcement', na=False),1,0)
df['analystReport'] = np.where(df['indicators'].str.contains('Analyst Report', na=False),1,0)
df['heaveNewsReporting'] = np.where(df['indicators'].str.contains('Heavy News Reporting', na=False),1,0)
df['gapDown'] = np.where(df['indicators'].str.contains('Gap Down', na=False),1,0)
df['gapUp'] = np.where(df['indicators'].str.contains('Gap Up', na=False),1,0)

df['callStockVolume'] = df['avgStockVolume'] / df['avgOptionVolume']

virt_daysToExpiration = 21
df['expirationDate'] = (pd.to_datetime(df['dataDate']) + timedelta(days=virt_daysToExpiration)).dt.strftime('%Y-%m-%d')
df.rename(columns={'exportedAt': 'exportedAtTimestamp',
                   'dataDate': 'exportedAt',
                   'ticker': 'baseSymbol'},
          inplace=True)

print('Null values: \n'.format(df.isna().sum()))
df.fillna(0, inplace=True)

print('Total train data shape: {}'.format(df.shape))
print('Minimum strike price increase: {}'.format(round((df['strikePrice'] / df['baseLastPrice']).min(), 2)))
print('Maximum strike price increase: {}'.format(round((df['strikePrice'] / df['baseLastPrice']).max(), 2)))
print('Minimum nr days until expiration: {}'.format(df['daysToExpiration'].min()))
print('Maximum nr days until expiration: {}'.format(df['daysToExpiration'].max()))

target = 'reachedStrikePrice'

# feature selection
features = ['callOptionVolume', 'avgOptionVolume',
            'increaseRelative2Avg', 'avgStockVolume',
            'firstPrice', 'indicatorPresent',
            'upcomingEarning', 'earningAnnounced', 'heaveNewsReporting', 'analystReport',
            'gapUp','gapDown','callStockVolume']

print('Nr of features included: {}'.format(len(features)))

########################
# Split in train and test
# test to split keeping exportedAt column always in same group
gss = GroupShuffleSplit(n_splits=1, train_size=.75, random_state=42)
gss.get_n_splits()

# split off test set
test_groupsplit = gss.split(df, groups = df['exportedAt'])
train_idx, test_idx = next(test_groupsplit)
df2 = df.loc[train_idx]
df_test = df.loc[test_idx]

# split off validation set
df2 = df2.reset_index(drop=True)
val_groupsplit = gss.split(df2, groups = df2['exportedAt'])
train_idx, val_idx = next(val_groupsplit)
df_train = df2.loc[train_idx]
df_val = df2.loc[val_idx]

# clean unwanted columns for model training
X_train = df_train[features]
y_train = df_train[target]

X_val = df_val[features]
y_val = df_val[target]

X_test = df_test[features]
y_test = df_test[target]

#####################
# Train
# Classifier
from sklearn.calibration import CalibratedClassifierCV, calibration_curve

train_type = 'PROD'
data_source = 'MB'
target_feature = '10p'
version = 'v1x0'
algorithm = 'GB'
if train_type == 'DEV':
    X_fit = X_train
    y_fit = y_train
    df_test = df_all.loc[X_test.index,:]
    df_test.to_csv("validation/test_df.csv")
elif train_type == 'PROD':
    X_fit = pd.concat([X_train, X_test])
    y_fit = pd.concat([y_train, y_test])

print('Train data shape: {}'.format(X_fit.shape))
print('Calibration data shape: {}'.format(X_val.shape))
print('Train type: {}\nVersion: {}\nAlgorithm: {}'.format(train_type, version, algorithm))
print('Training uncalibrated model...')

getwd = os.getcwd()
if algorithm == 'AB':
    params = {'n_estimators':1000, 'learning_rate':0.5, 'random_state':42}
    uncal_model = fit_AdaBoost(X_fit, y_fit, X_val, y_val, params, save_model = False, ab_path=getwd+'/trained_models/', name='{}_{}32_{}'.format(train_type, algorithm, version))
elif algorithm == 'GB':
    params = {'n_estimators':1000, 'learning_rate': 0.01, 'max_depth':4, 'random_state':42, 'subsample':0.8}
    uncal_model = fit_GBclf(X_fit, y_fit, X_val, y_val, params, save_model = False, gbc_path=getwd+'/trained_models/', name='{}_r_{}32_{}'.format(train_type, algorithm, version))

print('Training uncalibrated model... Done!')

xVar, yVar, thresholds = roc_curve(y_val, uncal_model.predict_proba(X_val)[:, 1])
roc_auc = auc(xVar, yVar)
print('Model has a ROC on validation set of: {}'.format(roc_auc))

print('Calibrate and save model...')
# calibrate and save classifier
cal_model = calibrate_model(uncal_model, X_val, y_val, method='sigmoid', save_model=True, path=getwd+'/trained_models/', name='{}_{}_{}_{}32_{}'.format(train_type, data_source, target_feature, algorithm, version))


print('Calibrate and save model... Done!')
