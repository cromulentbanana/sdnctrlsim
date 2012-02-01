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

./plot_timeseries.py -f ${LOGSDIR}/runsim.64.0.metrics ${LOGSDIR}/runsim.64.1.metrics ${LOGSDIR}/runsim.64.None.metrics
exit
$VIEWER ${LOGSDIR}/test_one_ctrl_simple.pdf 2>/dev/null &
./plot_timeseries.py -f ${LOGSDIR}/test_one_ctrl_simple.metrics
echo "Enter for next plot"
read
$VIEWER ${LOGSDIR}/test_two_ctrl_simple.pdf 2>/dev/null &
./plot_timeseries.py -f ${LOGSDIR}/test_two_ctrl_simple.metrics
echo "Enter for next plot"
read
./plot_timeseries.py -f ${LOGSDIR}/runsim.64.0.metrics ${LOGSDIR}/runsim.64.None.metrics
echo "Enter for next plot"
read
./plot_timeseries.py -f ${LOGSDIR}/runsim.64.0.metrics ${LOGSDIR}/runsim.64.1.metrics ${LOGSDIR}/runsim.64.None.metrics
echo "Enter for next plot"
read
# Greedy vs non-greedy
$VIEWER ${LOGSDIR}/greedy_corner_case_topo.pdf 2>/dev/null &
./plot_timeseries.py -f logs/runsim.64.None.metrics logs/runsim.greedy.64.None.1.metrics
echo "Enter for next plot"
read
./plot_timeseries.py -f logs/runsim.greedy.1.64.None.metrics logs/runsim.greedy.4.64.None.metrics
echo "Enter for next plot"
read
./plot_timeseries.py -f logs/runsim.greedy.1.64.None.metrics logs/runsim.greedy.2.64.None.metrics logs/runsim.greedy.3.64.None.metrics
echo "Enter for next plot"
read
./plot_timeseries.py -f logs/runsim.greedy.1.64.None.metrics logs/runsim.greedy.4.64.None.metrics
