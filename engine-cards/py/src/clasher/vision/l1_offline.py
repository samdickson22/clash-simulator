"""Process-local network guard for offline ML commands."""
import ipaddress
import os
import socket


def offline_ml(config_dir):
    """Disable library update probes/downloads before importing Ultralytics."""
    os.environ['YOLO_CONFIG_DIR']=str(config_dir)
    os.environ['YOLO_AUTOINSTALL']='false'
    original=socket.socket.connect

    def connect(sock,address):
        if sock.family in (socket.AF_INET,socket.AF_INET6):
            try:
                allowed=ipaddress.ip_address(address[0]).is_loopback
            except ValueError:
                allowed=False
            if not allowed:
                raise OSError('L1 offline ML process forbids external network connections')
        return original(sock,address)

    socket.socket.connect=connect
