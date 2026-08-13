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


def _repair_sheet_instances(sch_path):
    """Fill incomplete sheet_instances so kibot can load hierarchical schematics.

    Some KiCad 8 projects only store `(path "/" (page "1"))` while kibot/KiCad 10
    look up UUID paths like `/00000000-.../child-uuid`. Synthesize those entries
    from the root and sheet UUIDs already in the file.
    """
    import re

    try:
        with open(sch_path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"sheet_instances repair: could not read {sch_path}: {e}")
        return

    if "(sheet_instances" not in text:
        return

    root_m = re.search(r'^\s*\(uuid\s+"([^"]+)"', text, re.M)
    root_uuid = root_m.group(1) if root_m else None
    nil = "00000000-0000-0000-0000-000000000000"

    # Sheet block uuids (first uuid inside each (sheet ...))
    sheet_uuids = []
    for m in re.finditer(r'\(sheet\b', text):
        chunk = text[m.start(): m.start() + 2500]
        um = re.search(r'\(uuid\s+"([^"]+)"', chunk)
        if um:
            sheet_uuids.append(um.group(1))

    # Prefer page numbers from per-sheet instances when present
    page_by_sheet = {}
    for su in sheet_uuids:
        pm = re.search(
            rf'\(uuid\s+"{re.escape(su)}"[\s\S]*?\(instances[\s\S]*?\(page\s+"(\d+)"\)',
            text,
        )
        if pm:
            page_by_sheet[su] = pm.group(1)

    paths = []  # (path, page) unique order
    seen = set()

    def add(path, page):
        if path in seen:
            return
        seen.add(path)
        paths.append((path, page))

    add("/", "1")
    add(f"/{nil}", "1")
    if root_uuid:
        add(f"/{root_uuid}", "1")

    for i, su in enumerate(sheet_uuids):
        page = page_by_sheet.get(su, str(i + 2))
        add(f"/{nil}/{su}", page)
        if root_uuid:
            add(f"/{root_uuid}/{su}", page)

    body = "\n".join(
        f'\t\t(path "{p}"\n\t\t\t(page "{pg}")\n\t\t)' for p, pg in paths
    )
    new_block = f"(sheet_instances\n{body}\n\t)"
    new_text, n = re.subn(
        r"\(sheet_instances\b[\s\S]*?\n\t\)",
        new_block,
        text,
        count=1,
    )
    if n != 1:
        print(f"sheet_instances repair: no block replaced in {sch_path}")
        return
    with open(sch_path, "w", encoding="utf-8") as f:
        f.write(new_text)
    print(f"sheet_instances repair: wrote {len(paths)} paths for {os.path.basename(sch_path)}")


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
        sch_path = justNeedsExt + ".kicad_sch"
        pcb_path = justNeedsExt + ".kicad_pcb"

        if os.path.isfile(sch_path):
            _repair_sheet_instances(sch_path)

        cmd = [
            "kibot", "-c", str(config_path),
            "-e", sch_path,
            "-b", pcb_path,
            "-d", export_path,
            "--dont-stop",
        ]
        print(f"Running kibot for {name}: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)

        if result.returncode == 0 or _export_has_files(export_path):
            if result.returncode != 0:
                print(f"kibot exited {result.returncode} for {name} but produced output; treating as success")
            return None

        detail = (result.stderr or result.stdout or "").strip()
        # Prefer the last ERROR lines for the client-facing message
        err_lines = [
            ln for ln in detail.splitlines()
            if "ERROR:" in ln or "error:" in ln
        ]
        summary = " | ".join(err_lines[-5:]) if err_lines else detail
        return f"kibot failed (exit {result.returncode}): {summary[:2000] or 'no output'}"
    except Exception as e:
        print(f"Error rendering KiCAD project {name}: {traceback.format_exc()}")
        return f"{e}\n{traceback.format_exc()[-1500:]}"


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

