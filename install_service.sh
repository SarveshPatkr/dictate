#!/bin/bash
set -e

echo "🔧 Setting up Dictate Auto-Paste Service..."

# 1. Install ydotool if missing
if ! command -v ydotool &> /dev/null; then
    echo "Installing ydotool..."
    sudo apt install -y ydotool
fi

# 2. Add user to input group (to avoid sudo for key presses if configured right, 
# but usually ydotoold needs root. We will run ydotoold as a system service).

# 3. Create Systemd Service for ydotoold
echo "Creating system service for auto-paste..."

# We create a system-wide service so it has access to /dev/uinput
sudo bash -c 'cat > /etc/systemd/system/ydotoold.service <<EOF
[Unit]
Description=Ydotool Daemon (Virtual Input)
Wants=basic.target
After=basic.target

[Service]
ExecStart=/usr/bin/ydotoold --socket-path=/tmp/.ydotool_socket
Restart=always
# Run as root to access /dev/uinput
User=root
Group=root

[Install]
WantedBy=multi-user.target
EOF'

# 4. Reload and Start
echo "Starting service..."
sudo systemctl daemon-reload
sudo systemctl enable --now ydotoold.service

# 5. Make sure all users can write to the socket (so our script can talk to it)
echo "Configuring permissions..."
# Give it a second to start
sleep 2
sudo chmod 666 /tmp/.ydotool_socket

echo "✅ Done! Auto-paste should work now and survive reboots."
echo "Note: The socket is at /tmp/.ydotool_socket"
