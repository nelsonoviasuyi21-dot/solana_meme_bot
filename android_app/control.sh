#!/data/data/com.termux/files/usr/bin/bash
SERVICE="solana-bot"
SVDIR="$PREFIX/var/service"
while true; do
clear
echo "================================"
echo "     SOLANA MEME BOT"
echo "================================"
echo
SVDIR="$SVDIR" sv status "$SERVICE"
echo
echo "1. START BOT"
echo "2. STOP BOT"
echo "3. RESTART BOT"
echo "4. STATUS"
echo "5. EXIT"
echo
read -p "Choose: " choice
case "$choice" in
1) SVDIR="$SVDIR" sv up "$SERVICE";;
2) SVDIR="$SVDIR" sv down "$SERVICE";;
3) SVDIR="$SVDIR" sv restart "$SERVICE";;
4) SVDIR="$SVDIR" sv status "$SERVICE";;
5) exit 0;;
*) echo "Invalid choice"; sleep 1;;
esac
done
