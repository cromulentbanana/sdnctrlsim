#!/bin/bash
# A short script to automate what I plan to show Anja

./ctrlsim.py
./runsim.py

LOGSDIR="./logs"

case $(uname) in
	Darwin)
		VIEWER="open"
		;;
	Linux)
		VIEWER="evince"
		;;
esac

$VIEWER ${LOGSDIR}/test_one_ctrl_simple.pdf 2>/dev/null &
./plot_timeseries.py -f ${LOGSDIR}/test_one_ctrl_simple.metrics
echo "Enter for next plot"
read
$VIEWER ${LOGSDIR}/test_two_ctrl_simple.pdf 2>/dev/null &
./plot_timeseries.py -f ${LOGSDIR}/test_two_ctrl_simple.metrics
echo "Enter for next plot"
read
./plot_timeseries.py -f ${LOGSDIR}/runsim.16.0.metrics ${LOGSDIR}/runsim.16.31.metrics
echo "Enter for next plot"
read
./plot_timeseries.py -f ${LOGSDIR}/runsim.16.0.metrics ${LOGSDIR}/runsim.16.1.metrics ${LOGSDIR}/runsim.16.31.metrics
