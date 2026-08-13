# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

import os, subprocess, shutil, time, socket, threading, traceback
from pathlib import Path

# Add autobom to path so we can import socket_protocol
import sys
sys.path.insert(0, '/autobom/src')

from autobom.base.socket_protocol import (
    get_ecad_socket_address,
    send_message, receive_message,
    create_response, create_error,
    MSG_TYPE_REQUEST, REQ_RENDER,
    STATUS_SUCCESS, STATUS_FAILURE
)

export_options = ["step", "stl", "all"]

kicadIn = "/renderQueue/kicad/in/"
kicadOut = "/renderQueue/kicad/out/"

def _export_has_files(export_path):
    if not os.path.isdir(export_path):
        return False
    for root, _dirs, files in os.walk(export_path):
        if files:
            return True
    return False


def renderKicad(path, name):
    """Render a KiCAD project. Returns None on success, or an error string on failure."""
    try:
        os.makedirs(kicadOut, exist_ok=True)
        export_path = os.path.join(kicadOut, name)

        # delete previous export dir if still there
        if os.path.exists(export_path) and os.path.isdir(export_path):
            shutil.rmtree(export_path)

        os.makedirs(export_path)

        config_path = "/autobom/render/config.kibot.yaml"
        justNeedsExt = os.path.join(path, name)

        result = subprocess.run(
            [
                "kibot", "-c", str(config_path),
                "-e", justNeedsExt + ".kicad_sch",
                "-b", justNeedsExt + ".kicad_pcb",
                "-d", export_path,
            ],
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)

        if result.returncode == 0 or _export_has_files(export_path):
            if result.returncode != 0:
                print(f"kibot exited {result.returncode} for {name} but produced output; treating as success")
            return None

        detail = (result.stderr or result.stdout or "").strip()
        return f"kibot failed (exit {result.returncode}): {detail[:500] or 'no output'}"
    except Exception as e:
        print(f"Error rendering KiCAD project {name}: {traceback.format_exc()}")
        return str(e)


def handle_request(client_sock, addr):
    """Handle a render request from a client."""
    message = None
    try:
        message = receive_message(client_sock)
        if not message:
            return
        
        if message.get("type") != MSG_TYPE_REQUEST or message.get("request_type") != REQ_RENDER:
            error_msg = create_error(
                message.get("part_name", "unknown"),
                f"Invalid request type: {message.get('request_type')}",
                message.get("request_id")
            )
            send_message(client_sock, error_msg)
            return
        
        part_name = message.get("part_name")
        request_id = message.get("request_id")
        
        print(f"Received render request for {part_name}")
        
        # KiCAD projects are directories
        input_path = os.path.join(kicadIn, part_name)
        if not os.path.exists(input_path) or not os.path.isdir(input_path):
            error_msg = create_error(part_name, f"Directory not found: {input_path}", request_id)
            send_message(client_sock, error_msg)
            return
        
        err = renderKicad(input_path, part_name)
        if err is None:
            # Clean up input directory
            shutil.rmtree(input_path)
            response = create_response(
                request_id, STATUS_SUCCESS, part_name,
                output_dir=os.path.join(kicadOut, part_name)
            )
        else:
            # Still clean up input directory on failure
            try:
                shutil.rmtree(input_path)
            except Exception:
                pass
            response = create_response(
                request_id, STATUS_FAILURE, part_name,
                error=err
            )
        
        send_message(client_sock, response)
        print(f"Completed render request for {part_name}: {response['status']}")
        
    except Exception as e:
        print(f"Error handling request: {traceback.format_exc()}")
        try:
            error_msg = create_error(
                message.get("part_name", "unknown") if 'message' in locals() else "unknown",
                str(e),
                message.get("request_id") if 'message' in locals() else None
            )
            send_message(client_sock, error_msg)
        except Exception as send_error:
            print(f"Error sending error message: {send_error}")
    finally:
        try:
            client_sock.close()
        except:
            pass


def start_socket_server():
    """Start the socket server to listen for render requests."""
    host, port = get_ecad_socket_address(server=True)
    
    # Create TCP socket (works across Docker boundaries)
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(5)
    
    print(f"ECAD render server listening on {host}:{port}")
    
    while True:
        try:
            client_sock, addr = server_sock.accept()
            # Handle each request in a separate thread
            thread = threading.Thread(target=handle_request, args=(client_sock, addr))
            thread.daemon = True
            thread.start()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error accepting connection: {traceback.format_exc()}")
            continue
    
    server_sock.close()


if __name__ == "__main__":
    try:
        start_socket_server()
    except Exception as e:
        print(f"FATAL ERROR starting ECAD render server: {traceback.format_exc()}")
        sys.exit(1)

