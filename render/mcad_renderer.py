# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

import os, subprocess, sys, time, socket, json, struct, threading, traceback
from pathlib import Path

# Add autobom to path so we can import socket_protocol
sys.path.insert(0, '/autobom/src')

freecad_paths = [
    '/squashfs-root/usr/lib',
    '/squashfs-root/usr/lib/python3.11/site-packages',
    '/home/runner/work/feeder/feeder/squashfs-root/usr/lib',  # For CI when using AppImage
    '/usr/lib/freecad/lib/',  # For CI
    '/usr/lib/freecad-daily-python3/lib/',  # For Ubuntu
    '/usr/lib64/freecad/lib64/',  # For Fedora
    '/Applications/FreeCAD.app/Contents/MacOS/',  # For Mac OS X
    '/Applications/FreeCAD.app/Contents/Resources/lib',  # For Mac OS X
    '/Applications/FreeCAD.app/Contents/Resources/lib/python3.11/site-packages',
    'c:/Program Files/FreeCAD 0.18/bin/',  # For Windows
    'c:/Program Files/FreeCAD 0.19/bin/',  # For Windows
]

for path in freecad_paths:
    if os.path.exists(path):
        sys.path.append(path)

try:
    import FreeCAD
    import MeshPart
except ImportError as e:
    print(f"WARNING: Could not import FreeCAD: {e}")
    print("FreeCAD rendering will not be available, but OpenSCAD may still work.")
    FreeCAD = None
    MeshPart = None

from autobom.base.socket_protocol import (
    get_mcad_socket_address,
    send_message, receive_message,
    create_response, create_error,
    MSG_TYPE_REQUEST, REQ_RENDER,
    STATUS_SUCCESS, STATUS_FAILURE
)

export_options = ["step", "stl", "all"]

freecadIn = "/renderQueue/freecad/in/"
freecadOut = "/renderQueue/freecad/out/"

openscadIn = "/renderQueue/openscad/in/"
openscadOut = "/renderQueue/openscad/out/"

# FreeCAD (and OpenSCAD+Xvfb) are not safe to use from multiple threads.
_render_lock = threading.Lock()

def _shape_has_volume(shape):
    if shape is None or shape.isNull():
        return False
    try:
        return shape.Volume > 0
    except Exception:
        return False


def _find_export_shape(doc, name):
    """Find a solid shape to export from a FreeCAD document."""
    # Prefer PartDesign Body (by type or common label)
    bodies = [
        obj for obj in doc.Objects
        if obj.isDerivedFrom("PartDesign::Body") or obj.Label == "Body"
    ]
    for body in bodies:
        if _shape_has_volume(body.Shape):
            return body.Shape.copy(False)

    # Part containers (assemblies / multi-body parts)
    parts = [obj for obj in doc.Objects if obj.isDerivedFrom("Part::Feature") and hasattr(obj, "Shape")]
    for part in parts:
        if _shape_has_volume(part.Shape):
            return part.Shape.copy(False)

    # App::Part with child solids
    for obj in doc.Objects:
        if obj.isDerivedFrom("App::Part") and hasattr(obj, "Shape"):
            if _shape_has_volume(obj.Shape):
                return obj.Shape.copy(False)

    raise Exception(f"No exportable solid found in model {name}")


def renderFreecad(path, part_name):
    """Render a FreeCAD file. Returns None on success, or an error string on failure."""
    if FreeCAD is None:
        return "FreeCAD is not available (import failed at server startup)"
    doc = None
    try:
        # we just barf out an stl, step, and image
        doc = FreeCAD.open(path)
        name = Path(path).stem

        # Recompute the model to ensure its valid and does not contain broken references or edges
        for obj in doc.Objects:
            obj.touch()

        try:
            doc.recompute(None, True, True)
        except Exception as recompute_err:
            # 1.1.x files may warn on recompute; try to export anyway
            print(f"Recompute warning for {name}: {recompute_err}")

        shape = _find_export_shape(doc, name)

        # generate STEP
        shape.exportStep(freecadOut + name + ".step")

        # Generate STL (coarse deflection keeps memory down on GHA runners)
        mesh = doc.addObject("Mesh::Feature", "Mesh")
        mesh.Mesh = MeshPart.meshFromShape(
            Shape=shape,
            LinearDeflection=0.1,
            AngularDeflection=0.5,
            Relative=False,
        )
        mesh.Mesh.write(freecadOut + name + ".stl")

        # Preview PNG is best-effort; STEP/STL success still counts
        try:
            _renderImageFromSTL(name, freecadOut + name + ".stl", freecadOut)
        except Exception as img_err:
            print(f"Preview image failed for {name} (continuing): {img_err}")

        return None
    except Exception as e:
        print(f"Error rendering FreeCAD file {path}: {traceback.format_exc()}")
        return str(e)
    finally:
        if doc is not None:
            try:
                FreeCAD.closeDocument(doc.Name)
            except Exception:
                pass

def renderOpenscad(path, part_name):
    """Render an OpenSCAD file. Returns None on success, or an error string on failure."""
    try:
        _renderSTLFromOpenscad(path)
        try:
            _renderImageFromOpenscad(path)
        except Exception as img_err:
            print(f"Preview image failed for {part_name} (continuing): {img_err}")
        return None
    except Exception as e:
        print(f"Error rendering OpenSCAD file {path}: {traceback.format_exc()}")
        return str(e)

def _renderImageFromSTL(name, stlPath, outPath):

    scad_path = outPath + "render.scad"
    png_path = outPath + name + ".png"

    with open(scad_path, "w") as f:
        f.write(f'import("{stlPath}", convexity=3);')

    print("made openscad file, time to render image")

    result = subprocess.run(
        [
            "openscad",
            "-o", png_path,
            "--quiet",
            "--render",
            "--projection=o",
            "--viewall",
            "--colorscheme", "BeforeDawn",
            "--imgsize", "512,512",
            scad_path,
        ],
        capture_output=True,
        text=True,
    )
    try:
        os.remove(scad_path)
    except OSError:
        pass

    if result.returncode != 0 or not os.path.isfile(png_path) or os.path.getsize(png_path) == 0:
        raise RuntimeError(
            f"openscad png failed (exit {result.returncode}): "
            f"{(result.stderr or result.stdout or '').strip()[:500]}"
        )

def _renderSTLFromOpenscad(path):
    # takes no arguments, can only export stl
    name = os.path.splitext(os.path.basename(path))[0]
    subprocess.call(["openscad", "-o", openscadOut+name+".stl", path ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

def _renderImageFromOpenscad(path):
    name = os.path.splitext(os.path.basename(path))[0]
    subprocess.call(["openscad", "-o", openscadOut+name+".png", "--quiet", "--render", "--projection=o", "--viewall","--colorscheme","BeforeDawn", "--imgsize", "1028,1028", "--hardwarnings", path ], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

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
        file_type = message.get("file_type")  # "fcstd" or "scad"
        request_id = message.get("request_id")
        
        print(f"Received render request for {part_name} (type: {file_type})")

        with _render_lock:
            # Determine input path based on file type
            if file_type == "fcstd":
                input_path = os.path.join(freecadIn, part_name + ".FCStd")
                if not os.path.exists(input_path):
                    error_msg = create_error(part_name, f"File not found: {input_path}", request_id)
                    send_message(client_sock, error_msg)
                    return

                err = renderFreecad(input_path, part_name)
                if err is None:
                    # Clean up input file
                    os.remove(input_path)
                    response = create_response(
                        request_id, STATUS_SUCCESS, part_name,
                        output_dir=freecadOut
                    )
                else:
                    response = create_response(
                        request_id, STATUS_FAILURE, part_name,
                        error=err
                    )

            elif file_type == "scad":
                input_path = os.path.join(openscadIn, part_name + ".scad")
                if not os.path.exists(input_path):
                    error_msg = create_error(part_name, f"File not found: {input_path}", request_id)
                    send_message(client_sock, error_msg)
                    return

                err = renderOpenscad(input_path, part_name)
                if err is None:
                    # Clean up input file
                    os.remove(input_path)
                    response = create_response(
                        request_id, STATUS_SUCCESS, part_name,
                        output_dir=openscadOut
                    )
                else:
                    response = create_response(
                        request_id, STATUS_FAILURE, part_name,
                        error=err
                    )
            else:
                error_msg = create_error(part_name, f"Unknown file type: {file_type}", request_id)
                send_message(client_sock, error_msg)
                return

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
    print("Getting socket address...", file=sys.stderr)
    try:
        host, port = get_mcad_socket_address(server=True)
        print(f"Socket address: {host}:{port}", file=sys.stderr)
    except Exception as e:
        print(f"Error getting socket address: {e}", file=sys.stderr)
        raise
    
    print(f"Creating TCP socket server on {host}:{port}", file=sys.stderr)
    try:
        # Create TCP socket (works across Docker boundaries)
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print("Socket created", file=sys.stderr)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print("SO_REUSEADDR set", file=sys.stderr)
        server_sock.bind((host, port))
        print(f"Socket bound successfully to {host}:{port}", file=sys.stderr)
        server_sock.listen(5)
        print("Socket listening", file=sys.stderr)
    except Exception as e:
        print(f"Error setting up socket: {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        raise
    
    print(f"MCAD render server listening on {host}:{port}", file=sys.stderr)
    print("Ready to accept connections...", file=sys.stderr)
    
    while True:
        try:
            client_sock, addr = server_sock.accept()
            # Handle requests one at a time — FreeCAD is not thread-safe.
            handle_request(client_sock, addr)
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
        print(f"FATAL ERROR starting MCAD render server: {traceback.format_exc()}")
        sys.exit(1)
