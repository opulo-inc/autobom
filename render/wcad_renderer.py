# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

import os, subprocess, shutil, socket, threading, traceback

import sys
sys.path.insert(0, '/autobom/src')

from autobom.base.socket_protocol import (
    get_wcad_socket_address,
    send_message, receive_message,
    create_response, create_error,
    MSG_TYPE_REQUEST, REQ_RENDER,
    STATUS_SUCCESS, STATUS_FAILURE
)

wirevizIn = "/renderQueue/wireviz/in/"
wirevizOut = "/renderQueue/wireviz/out/"

_render_lock = threading.Lock()

WIREVIZ_OUTPUTS = (".png", ".svg", ".html", ".gv", ".bom.tsv")


def _find_yaml(indir, part_name):
    candidates = [
        os.path.join(indir, part_name + ".yml"),
        os.path.join(indir, part_name + ".yaml"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    if os.path.isdir(indir):
        for name in sorted(os.listdir(indir)):
            lower = name.lower()
            if lower.endswith(".yml") or lower.endswith(".yaml"):
                return os.path.join(indir, name)
    return None


def renderWireviz(indir, part_name):
    """Run WireViz. Returns None on success, or an error string on failure."""
    try:
        os.makedirs(wirevizOut, exist_ok=True)
        export_path = os.path.join(wirevizOut, part_name)
        if os.path.isdir(export_path):
            shutil.rmtree(export_path)
        os.makedirs(export_path)

        yaml_path = _find_yaml(indir, part_name)
        if not yaml_path:
            return f"No WireViz YAML found in {indir}"

        print(f"Running wireviz on {yaml_path}")
        result = subprocess.run(
            ["wireviz", yaml_path],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(yaml_path),
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)

        stem = os.path.splitext(os.path.basename(yaml_path))[0]
        src_dir = os.path.dirname(yaml_path)
        copied = []
        for suffix in WIREVIZ_OUTPUTS:
            src = os.path.join(src_dir, stem + suffix)
            if not os.path.isfile(src):
                continue
            dst_name = part_name + suffix
            shutil.copy2(src, os.path.join(export_path, dst_name))
            copied.append(dst_name)

        png = os.path.join(export_path, part_name + ".png")
        svg = os.path.join(export_path, part_name + ".svg")
        if result.returncode != 0 and not os.path.isfile(png) and not os.path.isfile(svg):
            detail = (result.stderr or result.stdout or "").strip()
            return f"wireviz failed (exit {result.returncode}): {detail[:2000] or 'no output'}"

        if result.returncode != 0:
            print(f"wireviz exited {result.returncode} for {part_name} but produced {copied}; treating as success")
        if not copied:
            return f"wireviz produced no png/svg for {part_name}"
        print(f"WireViz outputs for {part_name}: {copied}")
        return None
    except Exception as e:
        print(f"Error rendering WireViz project {part_name}: {traceback.format_exc()}")
        return f"{e}\n{traceback.format_exc()[-1500:]}"


def handle_request(client_sock, addr):
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

        with _render_lock:
            input_path = os.path.join(wirevizIn, part_name)
            if not os.path.isdir(input_path):
                error_msg = create_error(part_name, f"Directory not found: {input_path}", request_id)
                send_message(client_sock, error_msg)
                return

            err = renderWireviz(input_path, part_name)
            if err is None:
                try:
                    shutil.rmtree(input_path)
                except Exception:
                    pass
                response = create_response(
                    request_id, STATUS_SUCCESS, part_name,
                    output_dir=os.path.join(wirevizOut, part_name)
                )
            else:
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
                message.get("part_name", "unknown") if message else "unknown",
                str(e),
                message.get("request_id") if message else None
            )
            send_message(client_sock, error_msg)
        except Exception as send_error:
            print(f"Error sending error message: {send_error}")
    finally:
        try:
            client_sock.close()
        except Exception:
            pass


def start_socket_server():
    host, port = get_wcad_socket_address(server=True)
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(5)
    print(f"WCAD render server listening on {host}:{port}")

    while True:
        try:
            client_sock, addr = server_sock.accept()
            thread = threading.Thread(target=handle_request, args=(client_sock, addr))
            thread.daemon = True
            thread.start()
        except KeyboardInterrupt:
            break
        except Exception:
            print(f"Error accepting connection: {traceback.format_exc()}")
            continue

    server_sock.close()


if __name__ == "__main__":
    try:
        start_socket_server()
    except Exception:
        print(f"FATAL ERROR starting WCAD render server: {traceback.format_exc()}")
        sys.exit(1)
