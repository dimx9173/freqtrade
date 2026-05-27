#!/bin/zsh
echo "auto_download_data start at $(date)" >> user_data/logs/auto_crontab.log
HOME=/home/carlos
source ~/.miniconda3/etc/profile.d/conda.sh
cd $HOME/
#echo $(pwd)
conda activate py311
cd $HOME/pywork/freqtrade
#echo $(pwd)


#configs=(
#  "user_data/config/config_2.json"
#  "user_data/config/config_3.json"
#  "user_data/config/config_4.json"
#  "user_data/config/config_5.json"
#  "user_data/config/config_6.json"
#  "user_data/config/config_7.json"
#)
#TIME_RANGE=$(zsh get_time_range.sh 6)

#for config in "${configs[@]}"; do
#  freqtrade download-data --config "$config" --timerange $TIME_RANGE --timeframe 1m 5m 15m 30m 1h 4h 12h 1d
#done

python gen_pairlist.py
TIME_RANGE=$(zsh get_time_range.sh 6)
freqtrade download-data --exchange bybit --pairs-file user_data/config/coinmarketcap-pairs.json --timerange $TIME_RANGE --timeframe 1m 5m 15m 30m 1h 4h 12h 1d
TIME_RANGE=$(zsh get_time_range.sh 6)
freqtrade download-data --exchange binance --trading-mode futures --pairs-file user_data/config/coinmarketcap-future-pairs.json --timerange $TIME_RANGE --timeframe 1m 5m 15m 30m 1h 4h 12h 1d


#echo system time to log
echo "auto_download_data finished at $(date)" >> user_data/logs/auto_crontab.log
echo "-----------------------------" >> user_data/logs/auto_crontab.log
