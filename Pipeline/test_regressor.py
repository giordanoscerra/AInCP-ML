import hashlib
import os
import json
import pandas as pd
from sktime.base import BaseEstimator
from train_regressor import train_regressor
import joblib as jl
import numpy as np
from predict_samples import predict_samples
import datetime
import matplotlib
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import RepeatedKFold
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt

def test_regressor(data_folder, save_folder, train_indexes, test_indexes, mean_test_score, window_size):

    best_estimators_df = pd.read_csv(save_folder + 'best_estimators_results.csv', index_col=0).sort_values(by=['mean_test_score', 'std_test_score'], ascending=False)

    #estimators_specs_list = []
    #estimators_specs_list.append(best_estimators_df[best_estimators_df['method'] == 'concat'].iloc[0])
    #estimators_specs_list.append(best_estimators_df[best_estimators_df['method'] == 'ai'].iloc[0])
    #estimators_specs_list.append(best_estimators_df[best_estimators_df['method'] == 'difference'].iloc[0])
    #estimators_specs_list = [row for index, row in best_estimators_df[(best_estimators_df['mean_test_score'] >= 0.975) & (best_estimators_df['window_size'] == 600)].iterrows()]
    #estimators_specs_list = [row for index, row in best_estimators_df[(best_estimators_df['mean_test_score'] == 1) & (best_estimators_df['method'] == 'difference')].iterrows()]

    estimators_specs_list = [row for index, row in best_estimators_df[(best_estimators_df['mean_test_score'] >= mean_test_score) & (best_estimators_df['window_size'] == window_size)].iterrows()]


    print('Expected estimators: ',len(estimators_specs_list))
    estimators_list = []
    model_id_concat = ''

    for estimators_specs in estimators_specs_list:
        estimator_dir = save_folder + "Trained_models/" + estimators_specs['method'] + "/" + str(estimators_specs['window_size']) + "_seconds/" + estimators_specs['model_type'].split(".")[-1] + "/gridsearch_" + estimators_specs['gridsearch_hash']  + "/"

        with open(estimator_dir + 'GridSearchCV_stats/best_estimator_stats.json', "r") as stats_f:
            grid_search_best_params = json.load(stats_f)

        estimator = BaseEstimator().load_from_path(estimator_dir + 'best_estimator.zip')
        estimators_list.append({'estimator': estimator, 'method': estimators_specs['method'], 'window_size': estimators_specs['window_size'], 'hemi_cluster': grid_search_best_params['Hemi cluster']})
        print('Loaded -> ', estimator_dir + 'best_estimator.zip')
        model_id_concat = model_id_concat + estimator_dir

    print('Loaded estimators: ',len(estimators_list))

    metadata = pd.read_excel(data_folder + 'metadata2023_08.xlsx').iloc[test_indexes]
    metadata.drop(['age_aha', 'gender', 'dom', 'date AHA', 'start AHA', 'stop AHA'], axis=1, inplace=True)

    reg_path =  save_folder + 'Regressors/regressor_'+ (hashlib.sha256((model_id_concat).encode()).hexdigest()[:10])

    if not(os.path.exists(reg_path)):
        #Dobbiamo allenare il regressore
        print('INIZIO TRAINING REGRESSORE')
        train_regressor(data_folder, estimators_list, reg_path, train_indexes)

    regressor = jl.load(reg_path)
    print('REGRESSOR READY')

    sample_size = estimators_list[0]['window_size']

    stats_folder = save_folder + 'week_stats_' + str(sample_size) + '_' + str(len(estimators_list)) + 'est'
    os.makedirs(stats_folder, exist_ok=True)
    if not os.path.exists('timestamps_list'):
        start = datetime.datetime(2023, 1, 1)
        end = datetime.datetime(2023, 1, 7)
        step = datetime.timedelta(seconds=1)
        timestamps = []
        current = start
        while current < end:
            timestamps.append(matplotlib.dates.date2num(current))
            current += step
        jl.dump(timestamps, 'timestamps_list')
    else:
        timestamps = jl.load('timestamps_list')

    sample_size = estimators_list[0]['window_size']

    trend_block_size = int((60 * 60 * 6) / sample_size)  # Numero di finestre (da 300/600/900 secondi) raggruppate in un blocco da 6 ore
    significativity_threshold = 75                  # Percentuale di finestre in un blocco che devono essere prese per renderlo significativo

    plot_show = False
    '''
    answer = input("Do you want to see the dashboard for each patient? (yes/no): \n")
    # If the user enters "yes", show the plot
    if answer.lower() == "yes":
        plot_show = True
    '''

    healthy_percentage = []
    predicted_aha_list = []

    for i in range (1, metadata.shape[0]+1):
        predictions, hp_tot_list, magnitude_D, magnitude_ND = predict_samples(data_folder, estimators_list, i)
        healthy_percentage.append(hp_tot_list)
        real_aha = metadata['AHA'].iloc[i-1]
        predicted_aha = regressor.predict(np.array([hp_tot_list]))[0]
        predicted_aha = 100 if predicted_aha > 100 else predicted_aha
        predicted_aha_list.append(predicted_aha)

        temp_metadata = metadata.iloc[i-1]
        temp_metadata['healthy_percentage'] = hp_tot_list
        temp_metadata['predicted_aha'] = predicted_aha
        temp_metadata.to_frame().T.to_csv(stats_folder + '/predictions_dataframe_' + str(i) + '.csv', index = False)

        print('Patient ', i)
        print(' - AHA:     ', real_aha)
        print(' - HP:      ', hp_tot_list)
        print(' - AHA predicted from HP: ', predicted_aha)


        #################### ANDAMENTO WEEK GENERALE ####################

        # Fase di plotting
        fig, axs = plt.subplots(7)
        fig.suptitle('Patient ' + str(i) + ' week trend, AHA: ' + str(real_aha))
        #axs[0].xaxis.set_minor_locator(matplotlib.dates.HourLocator())
        #axs[0].xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(12))
        #axs[0].xaxis.set_minor_locator(matplotlib.ticker.AutoMinorLocator(n=6))
        #axs[0].xaxis.set_minor_formatter(matplotlib.dates.DateFormatter('%H-%M'))
        axs[0].xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%d-%H:%M'))
        axs[0].plot(timestamps, magnitude_D)
        axs[0].plot(timestamps, magnitude_ND)

        ########################## AI PLOT ##########################
        ai_list = []
        subList_magD = [magnitude_D[n:n+(trend_block_size*sample_size)] for n in range(0, len(magnitude_D), trend_block_size*sample_size)]
        subList_magND = [magnitude_ND[n:n+(trend_block_size*sample_size)] for n in range(0, len(magnitude_ND), trend_block_size*sample_size)]
        for l in range(len(subList_magD)):        
            if (subList_magD[l].mean() + subList_magND[l].mean()) == 0:
                ai_list.append(np.nan)
            else:
                ai_list.append(((subList_magD[l].mean() - subList_magND[l].mean()) / (subList_magD[l].mean() + subList_magND[l].mean())) * 100)

        axs[1].grid()
        #axs[1].set_ylim([-101,101])
        axs[1].plot(ai_list)

        #################### GRAFICO DEI PUNTI ####################
        for pred in predictions:
            axs[2].scatter(list(range(len(pred))), pred, c=pred, cmap='brg', s=1) 

        #################### ANDAMENTO A BLOCCHI ####################
        for pred in predictions:
            h_perc_list = []
            subList = [pred[n:n+trend_block_size] for n in range(0, len(pred), trend_block_size)]
            for l in subList:
                n_hemi = l.tolist().count(-1)
                n_healthy = l.tolist().count(1)
                if (((n_hemi + n_healthy) / trend_block_size) * 100) < significativity_threshold:
                    h_perc_list.append(np.nan)
                else:
                    h_perc_list.append((n_healthy / (n_hemi + n_healthy)) * 100)

            h_perc_list.append(h_perc_list[-1])
            axs[4].grid()
            axs[4].set_ylim([-1,101])
            axs[4].plot(h_perc_list, drawstyle = 'steps-post')
        
        ##################### ANDAMENTO SMOOTH ######################
        h_perc_list_smooth_list = []
        axs[5].grid()
        axs[5].set_ylim([-1,101])
        for pred in predictions:
            h_perc_list_smooth = []
            h_perc_list_smooth_significativity = []
            subList_smooth = [pred[n:n+trend_block_size] for n in range(0, len(pred)-trend_block_size+1)]
            for l in subList_smooth:
                n_hemi = l.tolist().count(-1)
                n_healthy = l.tolist().count(1)
                h_perc_list_smooth_significativity.append(((n_hemi + n_healthy) / trend_block_size) * 100)
                if (((n_hemi + n_healthy) / trend_block_size) * 100) < significativity_threshold:
                    h_perc_list_smooth.append(np.nan)
                else:
                    h_perc_list_smooth.append((n_healthy / (n_hemi + n_healthy)) * 100)

            axs[5].plot(h_perc_list_smooth)
            h_perc_list_smooth_list.append(h_perc_list_smooth)

        ##################### SIGNIFICATIVITY PLOT ####################

        axs[3].grid()
        axs[3].set_ylim([-1,101])
        axs[3].axhline(y = significativity_threshold, color = 'r', linestyle = '-', label='threshold')
        axs[3].plot(h_perc_list_smooth_significativity)
        axs[3].legend()

        ##################### PREDICTED AHA PLOT ####################


        aha_list_smooth = []
        for elements in zip(*h_perc_list_smooth_list):
            if np.isnan(elements[0]):
                aha_list_smooth.append(np.nan)
            else:
                predicted_window_aha = (regressor.predict(np.array([elements])))
                aha_list_smooth.append(predicted_window_aha if predicted_window_aha <= 100 else 100)

        conf = 5
        axs[6].grid()
        axs[6].set_ylim([-1,101])
        axs[6].axhline(y = real_aha, color = 'b', linestyle = '--', linewidth= 1, label='aha')
        axs[6].plot(aha_list_smooth, c = 'grey')
        axs[6].plot([x if real_aha + conf < x else np.nan for x in aha_list_smooth], c ='green')
        axs[6].plot([x if real_aha + 2*conf < x else np.nan for x in aha_list_smooth], c ='darkgreen')
        axs[6].plot([x if x < real_aha - conf else np.nan for x in aha_list_smooth], c ='orange')
        axs[6].plot([x if x < real_aha - 2*conf else np.nan for x in aha_list_smooth], c ='darkorange')
        axs[6].legend()
        #############################################################
        
        plt.savefig(stats_folder + '/subject_' +str(i)+'.png')

        if(plot_show == True):
            plt.show() 
        plt.close()

    if len(healthy_percentage) == metadata.shape[0] and len(predicted_aha_list) == metadata.shape[0]:
        metadata['healthy_percentage'] = healthy_percentage
        metadata['predicted_aha'] = predicted_aha_list
        metadata.to_csv(stats_folder + '/predictions_dataframe.csv')

    #metadata.plot.scatter(x='healthy_percentage', y='AHA', c='MACS', colormap='viridis').get_figure().savefig(stats_folder + 'plot_healthyPerc_AHA.png')
    #metadata.plot.scatter(x='healthy_percentage', y='AI_week', c='MACS', colormap='viridis').get_figure().savefig(stats_folder + 'plot_healthyPerc_AI_week.png')
    #metadata.plot.scatter(x='healthy_percentage', y='AI_aha', c='MACS', colormap='viridis').get_figure().savefig(stats_folder + 'plot_healthyPerc_AI_aha.png')

    corcoef_hp_aha = (np.corrcoef(metadata['healthy_percentage'], metadata['AHA'].values))[0][1]
    print("Coefficiente di Pearson tra hp e aha:          ", corcoef_hp_aha)

    composed_dataframe = pd.DataFrame()
    # Sperimentale per concatenare i CSV contenenti series
    for i in range(1, metadata.shape[0] + 1):
        composed_dataframe = pd.concat([composed_dataframe, pd.read_csv(stats_folder + '/predictions_dataframe_' + str(i) +'.csv', index_col = False)])

    #print(composed_dataframe)

    #composed_dataframe['CPI_list'] = [json.loads(string) for string in composed_dataframe['healthy_percentage']]
    CPI_list = [json.loads(string) for string in composed_dataframe['healthy_percentage']]
    composed_dataframe.drop(['healthy_percentage'], axis=1, inplace=True)

    #print(composed_dataframe)

    print(type(CPI_list))
    print(type(CPI_list[0]))
    print(type(CPI_list[0][0]))

    X = np.array(CPI_list)
    y = composed_dataframe['AHA'].values

    model = LinearRegression()

    #cv = ShuffleSplit(n_splits=5, test_size=0.2, random_state=0)
    #kf = KFold(n_splits=5, shuffle=True)

    rkf = RepeatedKFold(n_splits=5, n_repeats=100)

    score = cross_val_score(model, X, y, cv=rkf)

    print(score)
    print(np.average(score))
    print(score.mean())

    data = {
        "cross_val_score": score
    }

    # Writing to a JSON file
    with open(save_folder + 'regressor_stats.json', 'w') as file:
        json.dump(data, file, indent=4)

    #model.fit(X, y)

    #plt.scatter(composed_dataframe['AHA'].values, model.predict(X))

    #plt.grid()
    #plt.xlim([0, 120])
    #plt.ylim([0, 120])

    #plt.show()
    #plt.close()