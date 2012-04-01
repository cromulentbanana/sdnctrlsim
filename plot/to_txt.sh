#!/bin/bash
# RMSE timeseries
for i in sync_improves_metric_lbc_expo sync_improves_metric_lbc_wave sync_improves_metric_separate_expo sync_improves_metric_separate_wave; do 
	echo "../plot/json2txt.py -f ${i}_32_{00,01,02,04,08,16}_0.metrics -r > R_rmse_${i}_32_0.metrics"
	../plot/json2txt.py -f ${i}_32_{00,01,02,04,08,16}_0.metrics -r > R_rmse_${i}_32_0.metrics; 
done;

#Physical network View files
for i in sync_improves_metric*.metrics; do echo "$i; ../plot/json2txt.py -p -f $i to R_pnview_$i"; ../plot/json2txt.py -p -f $i > R_pnview_$i; done;
