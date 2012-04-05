#!/bin/bash

#Run the simulation for the evaluation cases we're currently using in our apper
echo "Running the Simulation..."
sleep 1
./runsim.py -d 32 -s 0

echo "Producing plots..."
sleep 1
cd logs

ln -s ../plot/ctrlsim.R
../plot/to_txt.sh
../plot/R_plots.sh

echo "Your Plot files are sitting as PDFs in /tmp/R_*.pdf"
