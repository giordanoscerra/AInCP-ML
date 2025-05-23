import json
import os
import hashlib
import itertools
import pandas as pd
from train_best_model import train_best_model

#import warnings 

#warnings.filterwarnings("ignore")

def train_select_classifiers(data_folder, save_folder, subjects_indexes, l_window_size = [300, 600, 900], l_method = ['concat','difference', 'ai']):

    kmeans_type = 'sktime.clustering.k_means.TimeSeriesKMeans'
    kmeans_params =  {'averaging_method': ['mean'], 'init_algorithm': ['kmeans++', 'forgy'], 'metric': ['euclidean', 'dtw'], 'n_clusters': [2]}
    kmeans = (kmeans_type, kmeans_params)

    kmedoids_type = 'sktime.clustering.k_medoids.TimeSeriesKMedoids'
    kmedoids_params = {'init_algorithm': ['forgy', 'random'], 'metric': ['euclidean', 'dtw'], 'n_clusters': [2]}
    kmedoids = (kmedoids_type, kmedoids_params)

    boss_type = 'sktime.classification.dictionary_based._boss.BOSSEnsemble'
    #boss_params = {'alphabet_size': [4], 'feature_selection': ['none'], 'max_ensemble_size': [500], 'max_win_len_prop': [1], 'min_window': [10], 'n_jobs': [1], 'random_state': [None], 'save_train_predictions': [False], 'threshold': [0.92], 'typed_dict': [True], 'use_boss_distance': [True]}
    boss_params = {'feature_selection': ['chi2', 'none']}
    boss = (boss_type, boss_params)

    shapedtw_type = 'sktime.classification.distance_based._shape_dtw.ShapeDTW'
    shapedtw_params =  {'shape_descriptor_function': ['raw', 'paa']}
    shapedtw = (shapedtw_type, shapedtw_params)

    l_gridsearch_specs =    [kmeans, kmedoids, boss, shapedtw]          # [kmeans, kmedoids, boss, shapedtw]

    estimators_l = []
    best_estimators_l = []

    for method, window_size, gridsearch_specs in itertools.product(l_method, l_window_size, l_gridsearch_specs):

        model_type, model_params = gridsearch_specs

        gridsearch_hash = hashlib.sha256(json.dumps(model_params, sort_keys=True).encode()).hexdigest()[:10]

        print('Method: ', method, '\nWindow size: ', window_size, '\nModel type: ', model_type, '\nGrid search params: ', model_params)

        gridsearch_folder = save_folder + "Trained_models/" + method + "/" + str(window_size) + "_seconds/" + model_type.split(".")[-1] + "/" + "gridsearch_" + gridsearch_hash + "/"

        if not(os.path.exists(gridsearch_folder + "best_estimator.zip")) or not(os.path.exists(gridsearch_folder + 'GridSearchCV_stats/cv_results.csv')):

            train_best_model(data_folder, subjects_indexes, gridsearch_folder, model_type, model_params, method, window_size)

        cv_results = pd.read_csv(gridsearch_folder + 'GridSearchCV_stats/cv_results.csv', index_col=0)
        cv_results.columns = cv_results.columns.str.strip()
        cv_results['method'] = method
        cv_results['window_size'] = window_size
        cv_results['model_type'] = model_type.split(".")[-1]
        cv_results['gridsearch_hash'] = gridsearch_hash

        estimators_l.append(cv_results)
        best_estimators_l.append(cv_results.iloc[[cv_results['rank_test_score'].argmin()]])

    estimators_df = pd.concat(estimators_l, ignore_index=True)
    best_estimators_df = pd.concat(best_estimators_l, ignore_index=True)

    estimators_df.sort_values(by=['mean_test_score', 'std_test_score'], ascending=False).to_csv(save_folder+'estimators_results.csv')
    best_estimators_df.sort_values(by=['mean_test_score', 'std_test_score'], ascending=False).to_csv(save_folder+'best_estimators_results.csv')