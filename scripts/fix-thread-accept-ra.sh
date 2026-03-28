#!/bin/bash
# Fix Thread/Matter offline issue on HAOS
# Run this script in HAOS host shell (Proxmox Console → login)
#
# Problem: HAOS sets ipv6 forwarding=1, which resets accept_ra to 0,
#          preventing HA from receiving Thread route advertisements.
# Solution: Set accept_ra=2 and persist via udev rule (survives HAOS updates).

set -e

IFACE="enp6s18"
RULE_FILE="/etc/udev/rules.d/90-thread-accept-ra.rules"

echo "=== 1. Current status ==="
echo "accept_ra = $(cat /proc/sys/net/ipv6/conf/$IFACE/accept_ra)"
echo "forwarding = $(cat /proc/sys/net/ipv6/conf/$IFACE/forwarding)"

echo ""
echo "=== 2. Setting accept_ra=2 ==="
sysctl -w net.ipv6.conf.$IFACE.accept_ra=2
echo "accept_ra = $(cat /proc/sys/net/ipv6/conf/$IFACE/accept_ra)"

echo ""
echo "=== 3. Creating persistent udev rule ==="
cat > "$RULE_FILE" << EOF
ACTION=="add", SUBSYSTEM=="net", KERNEL=="$IFACE", RUN+="/usr/sbin/sysctl -w net.ipv6.conf.$IFACE.accept_ra=2"
EOF
udevadm control --reload-rules
cat "$RULE_FILE"

echo ""
echo "=== Done! ==="
echo "accept_ra=2 is now active and will persist across HAOS updates."
echo ""
echo "Next steps:"
echo "  1. Power-cycle Border Routers (Apple TV + HomePods) for 30 seconds"
echo "  2. Restart Matter Server addon in HA"
echo "  3. Wait 2-3 minutes for devices to reconnect"


# # 1. 删除持久化 udev 规则                                                                                                      
# rm /etc/udev/rules.d/90-thread-accept-ra.rules                                                                                 
# udevadm control --reload-rules                                                                                                 
                                                                                                                                
# # 2. 恢复 accept_ra 为默认值 1         
# sysctl -w net.ipv6.conf.enp6s18.accept_ra=1