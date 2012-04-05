#!/bin/bash
R --no-save << EOF

source("ctrlsim.R")

# Timeseries slice
plot.single.file(file="R_pnview_sync_improves_metric_lbc_wave_32_16_0", n=4, do.ps=1)       
plot.single.file(file="R_pnview_sync_improves_metric_separate_wave_32_16_0", n=4, do.ps=1)
plot.single.file(file="R_pnview_sync_improves_metric_lbc_expo_32_16_0", n=4, do.ps=1)       
plot.single.file(file="R_pnview_sync_improves_metric_separate_expo_32_16_0", n=4, do.ps=1)

# Boxplots
plot.single.file(file="R_rmse_sync_improves_metric_lbc_wave_32_0", n=6, do.box=1, do.ts=0, do.ps=1)
plot.single.file(file="R_rmse_sync_improves_metric_separate_wave_32_0", n=6, do.box=1, do.ts=0, do.ps=1)
plot.single.file(file="R_rmse_sync_improves_metric_lbc_expo_32_0", n=6, do.box=1, do.ts=0, do.ps=1)
plot.single.file(file="R_rmse_sync_improves_metric_separate_expo_32_0", n=6, do.box=1, do.ts=0, do.ps=1)
EOF
