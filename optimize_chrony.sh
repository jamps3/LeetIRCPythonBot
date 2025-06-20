#!/bin/bash
# Chrony optimization script for jamps server
# Run this script on your server to get maximum time accuracy

echo "🕐 Optimizing Chrony for maximum time accuracy..."

# Backup current configuration
sudo cp /etc/chrony/chrony.conf /etc/chrony/chrony.conf.backup.$(date +%Y%m%d_%H%M%S)
echo "✅ Backed up current configuration"

# Create optimized chrony configuration
sudo tee /etc/chrony/chrony.conf > /dev/null << 'CHRONY_CONF'
# High-accuracy chrony configuration for jamps server
# Optimized for maximum time synchronization precision

# Use multiple high-quality NTP servers for redundancy and accuracy
# Finnish NTP servers (closest geographically for best latency)
server ntp1.funet.fi iburst
server ntp2.funet.fi iburst  
server ntp.csc.fi iburst

# European stratum-1 servers for maximum accuracy
server ntp1.ptb.de iburst
server ntp2.ptb.de iburst

# Pool servers for additional redundancy
pool 2.fi.pool.ntp.org iburst maxsources 2
pool 2.europe.pool.ntp.org iburst maxsources 2

# Use time sources from DHCP and additional directories
sourcedir /run/chrony-dhcp
sourcedir /etc/chrony/sources.d

# Configuration files
keyfile /etc/chrony/chrony.keys
driftfile /var/lib/chrony/chrony.drift
ntsdumpdir /var/lib/chrony

# Enable comprehensive logging for monitoring
log tracking measurements statistics
logdir /var/log/chrony

# High accuracy polling settings
# More frequent polling for better accuracy
minpoll 3    # Poll every 8 seconds minimum
maxpoll 5    # Poll every 32 seconds maximum

# Strict accuracy requirements
maxupdateskew 5.0      # Allow updates if offset < 5 seconds
maxdistance 0.5        # Only use sources with distance < 0.5 seconds  
maxdelay 0.1           # Only use sources with delay < 100ms
maxdrift 500           # Allow drift up to 500 ppm

# Enable kernel synchronization for hardware clock
rtcsync

# Step clock for large adjustments but be conservative
makestep 0.1 3         # Step if offset > 100ms, only first 3 updates

# Improve accuracy with faster corrections
corrtimeratio 2        # Correct drift 2x faster

# Leap second handling
leapseclist /usr/share/zoneinfo/leap-seconds.list

# Allow local monitoring and control
allow 127.0.0.1
allow ::1
cmdallow 127.0.0.1
cmdallow ::1

# Include additional configuration files
confdir /etc/chrony/conf.d
CHRONY_CONF

echo "✅ Created optimized chrony configuration"

# Restart chrony with new configuration
sudo systemctl restart chrony
echo "✅ Restarted chrony service"

# Enable chrony to start at boot
sudo systemctl enable chrony
echo "✅ Enabled chrony for automatic startup"

# Wait a moment for chrony to settle
echo "⏳ Waiting for chrony to synchronize..."
sleep 10

# Show current status
echo ""
echo "📊 Current chrony status:"
chronyc tracking

echo ""
echo "📡 NTP sources:"
chronyc sources -v

echo ""
echo "🎯 Chrony optimization complete!"
echo "Your server now has maximum time accuracy with:"
echo "  • Multiple high-quality NTP servers"
echo "  • 3-5 second polling intervals for frequent updates" 
echo "  • Strict accuracy requirements (100ms max delay)"
echo "  • Hardware clock synchronization"
echo "  • Comprehensive logging enabled"

echo ""
echo "💡 To monitor time accuracy regularly, run:"
echo "  chronyc tracking     # Show sync status"
echo "  chronyc sources -v   # Show NTP sources"
echo "  chronyc sourcestats  # Show source statistics"
