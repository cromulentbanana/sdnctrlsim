#!/bin/bash
set -e 

#Run the simulation for the evaluation cases we're currently using in our apper
echo "Producing plots... Hope you already ran the simulation!"
sleep 1
cd logs

ln -f -s ../plot/ctrlsim.R
../plot/to_txt.sh
../plot/R_plots.sh

echo "Your Plot files are sitting as PDFs in /tmp/R_*.pdf"
