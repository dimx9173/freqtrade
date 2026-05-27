#!/bin/zsh
month_ago=$1
if [[ "$(uname)" == "Darwin" ]]; then
    end_date=$(date +%Y%m%d)
    start_date=$(date -v -$month_ago"m" +%Y%m%d)
    time_range="$start_date-$end_date"
    echo $time_range
elif [[ "$(uname)" == "Linux" ]]; then
    yesterday=$(date -d "yesterday" +%Y-%m-%d)
    six_months_ago=$(date -d "$yesterday -$month_ago months" +%Y-%m-%d)
    formatted_start_date=$(date -d "$six_months_ago" +%Y%m%d)
    formatted_end_date=$(date -d "$yesterday" +%Y%m%d)
    result="$formatted_start_date-$formatted_end_date"
    echo "$result"
fi
