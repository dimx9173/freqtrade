#!/bin/zsh

HOME=/home/carlos
source ~/.miniconda3/etc/profile.d/conda.sh
cd $HOME/
echo $(pwd)
#conda activate py311;source $HOME/pywork/freqtrade/.venv/bin/activate;
conda activate py311
cd $HOME/pywork/freqtrade
echo $(pwd)

# 依序執行 Hyperopt，完成後各策略會由 hyperopt.sh 內部呼叫 scripts/stop_by_config.sh
# 讓監控腳本偵測停止並自動重啟。此處不再呼叫 reload_config。
zsh hyperopt.sh 12 > user_data/logs/auto_crontab.log
#zsh hyperopt.sh 3 >> user_data/logs/auto_crontab.log
