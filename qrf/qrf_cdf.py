# -*- coding: utf-8 -*-
"""
Created on Sat Feb  9 11:36:03 2019

@author: Rui Li
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from skgarden import RandomForestQuantileRegressor
from dcdr.deep_hist import Binning_CDF
from dcdr.utils import evaluate_crps, \
evaluate_quantile_loss, evaluate_rmse, evaluate_coverage, quantile_to_cdf

class QRFCDF(RandomForestQuantileRegressor):
    
    def __init__(self, **kwargs):        
        super(QRFCDF, self).__init__(**kwargs) 
        
    
    def fit_cdf(self, train_x, train_y):
        
        train_x = np.array(train_x)
        train_y = np.array(train_y).flatten()
        
        if train_x.ndim < 2:
            train_x = train_x.reshape(-1, 1)
            
        self.p  = train_x.shape[1]
        self.y_min = np.min(train_y)
        self.y_max = np.max(train_y)
        self.y_range = self.y_max - self.y_min
        
        self.fit(train_x, train_y)
        
    def predict_cdf(self, test_x, quantiles_grid=None, quantile_lim=[0.00001, 0.99999],
                    n_quantiles=500, y_grid=None, pred_margin=0.1, ngrid=1000, 
                    keep_cdf_matrix=True, overwrite_y_grid=True, keep_test_x=True):
        
        if y_grid is None:
            self.pred_lim = [self.y_min - pred_margin*self.y_range, self.y_max + pred_margin*self.y_range]
            y_grid = np.linspace(self.pred_lim[0], self.pred_lim[1], num=ngrid)
            
        if not isinstance(test_x, np.ndarray):
            test_x = np.array(test_x)
            
        if test_x.ndim <2:
            test_x = test_x.reshape(-1, self.p)
            
        y_grid = y_grid.flatten()
        
        if quantiles_grid is None:
            quantiles_grid = np.linspace(quantile_lim[0], quantile_lim[1], num=n_quantiles)
        
        if keep_test_x:
            self.test_x = test_x

        if isinstance(quantiles_grid, list):
            rescaled_qt = [qt*100 for qt in quantiles_grid]
        else:
            rescaled_qt = quantiles_grid*100
        
        quantile_output = self.predict(test_x, quantile=rescaled_qt)
        
        TestX_CDF_matrix = quantile_to_cdf(quantile_output, quantiles_grid, y_grid)
            
        if keep_cdf_matrix:
            self.TestX_CDF_matrix = TestX_CDF_matrix
            
        if overwrite_y_grid:
            self.y_grid = y_grid
            
        cdf_df = pd.DataFrame(TestX_CDF_matrix, columns=y_grid)
         
        return cdf_df
     
    def plot_cdf(self, index=0, test_x=None, test_y=None, grid=None, pred_margin=0.1,
                 true_cdf_func=None, figsize=(12, 8), title=None):
        
        if test_x is None:
            cdf = self.TestX_CDF_matrix[index, :].copy()
            xval = self.test_x[index, :]
            grid = self.y_grid.copy()
        else:
            cdf = self.predict_cdf(test_x, y_grid=grid, pred_margin=pred_margin,
                                   keep_cdf_matrix=False, 
                                   overwrite_y_grid=True,
                                   keep_test_x=False).values.flatten()
            xval = test_x
            grid = self.y_grid.copy()
        
        cdf = cdf[grid.argsort()]
        grid.sort()
        
        fig, ax = plt.subplots(1, 1, figsize=figsize)
        ax.plot(grid, cdf, label='predicted cdf', lw=3)
        
        if true_cdf_func is not None:
            true_cdf = true_cdf_func(xval, grid)
            ax.plot(grid, true_cdf, label='true cdf', lw=3)
            
        ax.legend(loc='best', prop={'size':16})
        
        if test_y is not None:
            if test_x is None:
                ax.axvline(x=test_y[index], color='black',  lw=3)
            else:
                ax.axvline(x=test_y, color='black', lw=3)

        if title:
            ax.set_title(title, fontsize=20)
            tlt = ax.title
            tlt.set_position([0.5, 1.02])
            
        ax.get_xaxis().set_tick_params(direction='out', labelsize=16)
        ax.get_yaxis().set_tick_params(direction='out', labelsize=16)
            
        ax.set_xlim(self.pred_lim)
        
        return ax

         
    def plot_density(self, index=0, test_x=None, test_y=None, grid=None, pred_margin=0.1, 
                     window=1, true_density_func=None, figsize=(12, 8), title=None):

        if test_x is None:
            cdf = self.TestX_CDF_matrix[index, :].copy()
            xval = self.test_x[index, :]
            grid = self.y_grid.copy()

        else:
            cdf = self.predict_cdf(test_x, y_grid=grid, pred_margin=pred_margin,
                                   keep_cdf_matrix=False, 
                                   overwrite_y_grid=True,
                                   keep_test_x=False).values.flatten()
            xval = test_x
            grid = self.y_grid.copy()
            
            
        if len(grid) < 2*window + 1:
            raise ValueError('''The density of the most left {0} and the most right {1} 
                             grid points won't be plotted, so it requires at least 
                             {2} grid points to make density plot'''.format(window, window, 2*window + 1))        
        
        cdf = cdf[grid.argsort()]
        grid.sort()
        
        density_binwidth = grid[(2*window):] - grid[:-(2*window)]
        cdf_diff = cdf[(2*window):] - cdf[:-(2*window)]
        
        density = cdf_diff/density_binwidth
        
        fig, ax = plt.subplots(1, 1, figsize=figsize)
        ax.plot(grid[window:-window], density, label='predicted density', lw=3)
        
        if true_density_func is not None:
            true_density = true_density_func(xval, grid[window:-window])
            ax.plot(grid[window:-window], true_density, label='true density', lw=3)
            
        ax.legend(loc='best', prop={'size':16})
            
        if title:
            ax.set_title(title, fontsize=20)
            tlt = ax.title
            tlt.set_position([0.5, 1.02])
        
        if test_y is not None:
            if test_x is None:
                ax.axvline(x=test_y[index], color='black',  lw=3)
            else:
                ax.axvline(x=test_y, color='black', lw=3)
            
        ax.get_xaxis().set_tick_params(direction='out', labelsize=16)
        ax.get_yaxis().set_tick_params(direction='out', labelsize=16)
        
        ax.set_xlim(self.pred_lim)
        
        return ax          
    
    def predict_quantile(self, test_x, quantiles):
        
        if isinstance(quantiles, list):
            rescaled_qt = [qt*100 for qt in quantiles]
        else:
            rescaled_qt = quantiles*100
        
        quantile_output = self.predict(test_x, quantile=rescaled_qt)

        test_qt_df = pd.DataFrame(quantile_output, columns=quantiles)

        return test_qt_df
    
    def predict_mean(self, test_x):
        
        test_mean = self.predict(test_x)
        
        return test_mean
            
    def evaluate(self, test_x, test_y, y_grid=None, pred_margin=0.1, 
                 ngrid=1000, quantiles=None, interval=None, mode='CRPS'):
        
        if mode == 'QuantileLoss' and quantiles is not None:
            quantile_matrix = self.predict_quantile(test_x, quantiles).values
            test_score = evaluate_quantile_loss(quantile_matrix, test_y, quantiles)
        else:
            cdf_matrix = self.predict_cdf(test_x, y_grid=y_grid, 
                                          pred_margin=pred_margin,
                                          ngrid=ngrid).values                   
            if mode == 'CRPS':
                test_score = evaluate_crps(cdf_matrix, test_y, self.y_grid)
            elif mode == 'RMSE':            
                test_score = evaluate_rmse(cdf_matrix, test_y, self.y_grid)
            elif mode == 'Coverage' and interval is not None:
                test_score = evaluate_coverage(cdf_matrix, test_y, interval, self.y_grid)
        
        return test_score  