#!/bin/bash
# Daily chrony monitoring and sync verification script
# This script checks chrony status and logs time accuracy

LOGFILE="/var/log/chrony/daily_sync_check.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$DATE] Daily chrony sync check started" >> $LOGFILE

# Check if chrony is running
if ! systemctl is-active --quiet chrony; then
    echo "[$DATE] ERROR: Chrony service is not running!" >> $LOGFILE
    systemctl restart chrony
    echo "[$DATE] Restarted chrony service" >> $LOGFILE
fi

# Get tracking information
TRACKING=$(chronyc tracking 2>/dev/null)
if [ $? -eq 0 ]; then
    # Extract system time offset
    OFFSET=$(echo "$TRACKING" | grep "System time" | awk '{print $4}')
    RMS_OFFSET=$(echo "$TRACKING" | grep "RMS offset" | awk '{print $4}')
    STRATUM=$(echo "$TRACKING" | grep "Stratum" | awk '{print $3}')
    
    echo "[$DATE] Sync Status: Stratum $STRATUM, Offset: $OFFSET, RMS: $RMS_OFFSET" >> $LOGFILE
    
    # Check if offset is too large (> 1ms)
    OFFSET_NUM=$(echo $OFFSET | sed 's/[^0-9.-]//g')
    if [ $(echo "$OFFSET_NUM > 0.001" | bc -l 2>/dev/null || echo "0") -eq 1 ]; then
        echo "[$DATE] WARNING: Large time offset detected ($OFFSET)" >> $LOGFILE
    fi
else
    echo "[$DATE] ERROR: Cannot get chrony tracking information" >> $LOGFILE
fi

# Check source statistics
SOURCES=$(chronyc sources -v 2>/dev/null | grep "^\^[*+]" | wc -l)
if [ "$SOURCES" -gt 0 ]; then
    echo "[$DATE] Active sources: $SOURCES" >> $LOGFILE
else
    echo "[$DATE] WARNING: No active NTP sources!" >> $LOGFILE
fi

# Force a sync check (burst mode)
chronyc burst 4/4 &>/dev/null

echo "[$DATE] Daily chrony sync check completed" >> $LOGFILE
echo "" >> $LOGFILE
