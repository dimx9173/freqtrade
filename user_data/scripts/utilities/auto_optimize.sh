#!/bin/zsh

HOME=/home/brian
# source ~/.miniconda3/etc/profile.d/conda.sh
cd $HOME/
echo $(pwd)
#conda activate py311;source $HOME/pywork/freqtrade/.venv/bin/activate;
cd $HOME/freqtrade
source .venv/bin/activate;
#conda activate py312
echo $(pwd)

# 依序執行 Hyperopt，完成後各策略會由 hyperopt.sh 內部呼叫 scripts/stop_by_config.sh
# 讓監控腳本偵測停止並自動重啟。此處不再呼叫 reload_config。
zsh user_data/scripts/utilities/hyperopt.sh 6 > user_data/logs/auto_crontab.log
#zsh hyperopt.sh 3 >> user_data/logs/auto_crontab.log
