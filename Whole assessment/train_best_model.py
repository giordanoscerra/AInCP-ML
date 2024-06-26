import os
import json
import importlib
import pandas as pd
from sklearn.model_selection import StratifiedKFold
from sklearn.model_selection import GridSearchCV
from sktime.classification.base import BaseClassifier
from sktime.clustering.base import BaseClusterer
from sklearn.metrics import f1_score
from create_windows import create_windows
import sys

def scorer_f(estimator, X_train, Y_train):
    y_pred = estimator.predict(X_train)
    if issubclass(type(estimator), BaseClassifier):
        return f1_score(Y_train, y_pred, average='weighted')
    else:
        inverted_y_pred = [1 if item == 0 else 0 for item in y_pred]
        return max(f1_score(Y_train, y_pred, average='weighted'),f1_score(Y_train, inverted_y_pred, average='weighted'))

def train_best_model(data_folder, subjects_indexes, gridsearch_folder, model_type, model_params, method, window_size):

    # Split the string into the module and class names
    module_name, class_name = model_type.rsplit(".", 1)
    model = getattr(importlib.import_module(module_name), class_name)()

    X, _, _, y = create_windows(data_folder, subjects_indexes, method, window_size)
 
    param_grid = model_params
    #                                                             dobbiamo fixare il seed?
    parameter_tuning_method = GridSearchCV(model, param_grid, cv=StratifiedKFold(n_splits=5, shuffle=True), n_jobs=-1, return_train_score=True, verbose=3, scoring=scorer_f)
    parameter_tuning_method.fit(X, y)

    estimator = parameter_tuning_method.best_estimator_

    hemi_cluster = 1
    y_pred = estimator.predict(X)
    inverted_y_pred = [1 if item == 0 else 0 for item in y_pred]

    if issubclass(type(estimator), BaseClusterer) and f1_score(y, y_pred, average='weighted') < f1_score(y, inverted_y_pred, average='weighted'):
        hemi_cluster = 0

    # print('y = ', y)
    # print('y_pred = ', y_pred)
    # print('f1_score = ', f1_score(y, y_pred, average='weighted'))
    # print('f1_score (inverted) = ', f1_score(y, inverted_y_pred, average='weighted'))
    # print('hemi_cluster = ', hemi_cluster, ' (1 = non invertito)')

    stats_folder = gridsearch_folder + 'GridSearchCV_stats/'
    os.makedirs(stats_folder, exist_ok = True)
    pd.DataFrame(parameter_tuning_method.cv_results_).to_csv(stats_folder + "cv_results.csv")
    
    with open(stats_folder + 'best_estimator_stats.json', 'w') as f:
        f.write(json.dumps({"Best index":int(parameter_tuning_method.best_index_), "Best score":parameter_tuning_method.best_score_, "Refit time":parameter_tuning_method.refit_time_, "Best params": parameter_tuning_method.best_params_, "Hemi cluster": hemi_cluster}, indent=4))

    estimator.save(gridsearch_folder + "best_estimator")
    print('Best estimator saved\n\n------------------------------------------------\n')
    sys.stdout.flush()
    sys.stderr.flush()