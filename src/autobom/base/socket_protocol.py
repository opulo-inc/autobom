# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

"""
Socket protocol for communication between builder and render engines.
Uses TCP sockets with JSON messages (Unix sockets don't work on macOS Docker volumes).
"""

import json
import socket
import struct
import os
from typing import Optional, Dict, Any

# Use TCP sockets instead of Unix sockets for Docker compatibility
# Unix sockets don't work on macOS Docker volumes
# Server bind address (in containers) - use 0.0.0.0 to listen on all interfaces
MCAD_SOCKET_SERVER_HOST = "0.0.0.0"
MCAD_SOCKET_PORT = 9001
ECAD_SOCKET_SERVER_HOST = "0.0.0.0"
ECAD_SOCKET_PORT = 9002

# Client connect address (on host) - use 127.0.0.1 to connect via Docker port forwarding
MCAD_SOCKET_CLIENT_HOST = "127.0.0.1"
ECAD_SOCKET_CLIENT_HOST = "127.0.0.1"


def get_mcad_socket_address(ab_path: Optional[str] = None, server: bool = False) -> tuple:
    """Get the MCAD socket address (host, port).
    
    Args:
        ab_path: Unused, kept for compatibility
        server: If True, return server bind address (0.0.0.0), else client connect address (127.0.0.1)
    """
    if server:
        return (MCAD_SOCKET_SERVER_HOST, MCAD_SOCKET_PORT)
    return (MCAD_SOCKET_CLIENT_HOST, MCAD_SOCKET_PORT)


def get_ecad_socket_address(ab_path: Optional[str] = None, server: bool = False) -> tuple:
    """Get the ECAD socket address (host, port).
    
    Args:
        ab_path: Unused, kept for compatibility
        server: If True, return server bind address (0.0.0.0), else client connect address (127.0.0.1)
    """
    if server:
        return (ECAD_SOCKET_SERVER_HOST, ECAD_SOCKET_PORT)
    return (ECAD_SOCKET_CLIENT_HOST, ECAD_SOCKET_PORT)

# Message types
MSG_TYPE_REQUEST = "request"
MSG_TYPE_RESPONSE = "response"
MSG_TYPE_ERROR = "error"

# Request types
REQ_RENDER = "render"
REQ_STATUS = "status"

# Response statuses
STATUS_SUCCESS = "success"
STATUS_FAILURE = "failure"
STATUS_PROCESSING = "processing"


def send_message(sock: socket.socket, message: Dict[str, Any]) -> None:
    """Send a JSON message over the socket with length prefix."""
    data = json.dumps(message).encode('utf-8')
    length = len(data)
    # Send length as 4-byte big-endian integer
    sock.sendall(struct.pack('>I', length))
    sock.sendall(data)


def receive_message(sock: socket.socket) -> Optional[Dict[str, Any]]:
    """Receive a JSON message from the socket."""
    try:
        # Receive length prefix
        length_data = b''
        while len(length_data) < 4:
            chunk = sock.recv(4 - len(length_data))
            if not chunk:
                return None
            length_data += chunk
        
        length = struct.unpack('>I', length_data)[0]
        
        # Receive message data
        data = b''
        while len(data) < length:
            chunk = sock.recv(length - len(data))
            if not chunk:
                return None
            data += chunk
        
        return json.loads(data.decode('utf-8'))
    except (ConnectionResetError, ConnectionAbortedError, OSError) as e:
        # Connection was reset or closed
        return None
    except json.JSONDecodeError as e:
        # Invalid JSON received
        return None


def create_request(request_type: str, part_name: str, **kwargs) -> Dict[str, Any]:
    """Create a request message."""
    return {
        "type": MSG_TYPE_REQUEST,
        "request_type": request_type,
        "part_name": part_name,
        **kwargs
    }


def create_response(request_id: Optional[str], status: str, part_name: str, **kwargs) -> Dict[str, Any]:
    """Create a response message."""
    return {
        "type": MSG_TYPE_RESPONSE,
        "request_id": request_id,
        "status": status,
        "part_name": part_name,
        **kwargs
    }


def create_error(part_name: str, error_message: str, request_id: Optional[str] = None) -> Dict[str, Any]:
    """Create an error message."""
    return {
        "type": MSG_TYPE_ERROR,
        "request_id": request_id,
        "part_name": part_name,
        "error": error_message
    }
