# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

import os, copy, glob, sys, time, shutil, socket, uuid

from ..base.logger import Logger
from ..base.socket_protocol import (
    get_mcad_socket_address,
    send_message, receive_message,
    create_request, STATUS_SUCCESS, STATUS_FAILURE
)

export_options = ["step", "stl", "all"]


def raw_source_url(source_url, sha, repo_path, file_path):
    """GitHub raw URL for a file at this commit (the blob page is HTML, not the file)."""
    rel = os.path.relpath(file_path, repo_path).replace(os.sep, "/")
    base = (source_url or "").rstrip("/")
    if "github.com/" in base:
        repo = base.split("github.com/", 1)[1]
        return f"https://raw.githubusercontent.com/{repo}/{sha}/{rel}"
    return f"{base}/{rel}"


class MCAD():

    # Large FCStd files (e.g. x-gantry-back ~60MiB) can take many minutes.
    RENDER_TIMEOUT_S = 1800

    def __init__(self, part_info, settings, sha, repoPath, abPath):

        self.part_info = part_info
        self.settings = settings
        self.path = None
        self.name = part_info["name"]
        self.sha = sha
        self.repoPath = repoPath
        self.abPath = abPath
        self.last_error = None
            

    def out(self, manifest):
        """Export/render this part. Returns True on success, False on failure."""
        self.last_error = None
        #using default settings, but allowing part-specific to override
        render_method = self.settings["mcad"]["render"]
        if "render" in self.part_info:
            render_method = self.part_info["render"]

        export_method = self.settings["mcad"]["export"]
        if "export" in self.part_info:
            export_method = self.part_info["export"]

        # checking type

        base, ext = os.path.splitext(self.path)
        if ext.lower() == ".fcstd":
            if self.outFreecad(render_method, export_method, manifest):
                Logger.info(f"Exported and rendered {self.part_info['name']}")
                return True
            Logger.warn(f"Failed to export or render {self.part_info['name']}: {self.last_error}")
            return False

        elif ext.lower() == ".scad":
            if self.outOpenscad(render_method, export_method, manifest):
                Logger.info(f"Exported and rendered {self.part_info['name']}")
                return True
            Logger.warn(f"Failed to export or render {self.part_info['name']}: {self.last_error}")
            return False

        else:
            self.last_error = f"Found file {base}{ext} but {ext} files are not supported."
            Logger.warn(self.last_error)
            return False


    def outFreecad(self, render_method, export_method, manifest):
        Logger.info(f"Rendering FreeCAD file: {self.name}")
        try:
            size_mb = os.path.getsize(self.path) / (1024 * 1024)
            Logger.info(f"Source {self.path} ({size_mb:.1f} MiB)")
        except OSError:
            pass

        # Copy file to render queue input directory
        renderInputPath = self.abPath + "/renderQueue/freecad/in/" + self.name + ".FCStd"
        os.makedirs(os.path.dirname(renderInputPath), exist_ok=True)
        # Remove existing file if it exists (from previous failed run)
        if os.path.exists(renderInputPath):
            os.remove(renderInputPath)
        shutil.copyfile(self.path, renderInputPath)

        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Connect to render server via TCP socket
        host, port = get_mcad_socket_address(self.abPath)
        
        # Wait for server to be ready (try connecting a few times)
        max_retries = 20
        retry_interval = 0.5
        client_sock = None
        
        for attempt in range(max_retries):
            try:
                client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_sock.settimeout(2)
                client_sock.connect((host, port))
                client_sock.settimeout(self.RENDER_TIMEOUT_S)
                break
            except (ConnectionRefusedError, OSError):
                if client_sock:
                    client_sock.close()
                if attempt < max_retries - 1:
                    time.sleep(retry_interval)
                else:
                    self.last_error = (
                        f"Could not connect to FreeCAD render server at {host}:{port} "
                        f"after {max_retries} attempts (is docker-compose up?)"
                    )
                    Logger.warn(self.last_error)
                    return False
        
        try:
            # Send render request
            request = create_request(
                "render",
                self.name,
                request_id=request_id,
                file_type="fcstd"
            )
            send_message(client_sock, request)
            Logger.info(f"Sent render request for {self.name} (timeout {self.RENDER_TIMEOUT_S}s)")
            
            # Wait for response
            response = receive_message(client_sock)
            client_sock.close()
            
            if not response:
                self.last_error = "No response received from FreeCAD render server"
                Logger.warn(f"{self.name}: {self.last_error}")
                return False
            
            if response.get("status") != STATUS_SUCCESS:
                self.last_error = response.get("error", "Unknown error")
                Logger.warn(f"Render failed for {self.name}: {self.last_error}")
                return False
            
            Logger.info(f"Render completed successfully for {self.name}")
            
        except socket.timeout:
            self.last_error = (
                f"Timeout after {self.RENDER_TIMEOUT_S}s waiting for FreeCAD render. "
                f"Large/complex models may need more time or more RAM."
            )
            Logger.warn(f"{self.name}: {self.last_error}")
            return False
        except ConnectionRefusedError:
            self.last_error = f"Connection refused to FreeCAD render server at {host}:{port}"
            Logger.warn(self.last_error)
            Logger.warn("Check container logs: docker-compose -f docker-compose-local.yaml logs freecad")
            return False
        except Exception as e:
            self.last_error = f"Error communicating with FreeCAD render server: {e}"
            Logger.warn(f"{self.name}: {self.last_error}")
            Logger.warn(f"Check container logs: docker-compose -f docker-compose-local.yaml logs")
            return False

        # Copy output files to export directory
        try:
            exportFiles = os.listdir(self.abPath + "/renderQueue/freecad/out")
            for file in exportFiles:
                source_file = os.path.join(self.abPath + "/renderQueue/freecad/out", file)
                if os.path.isfile(source_file):
                    shutil.copy(source_file, self.repoPath + "/autobom/export")
                    os.remove(source_file)
        except Exception as e:
            self.last_error = f"Error copying FreeCAD export files: {e}"
            Logger.warn(f"{self.name}: {self.last_error}")
            return False

        #================
        # UPDATE MANIFEST
        #================

        part_manifest = copy.deepcopy(self.part_info)

        render = {"method_preference": "", "img_path": "", "3d_path": ""}

        if render_method == "src":
            render["method_preference"] = "3d"
            render["3d_path"] = raw_source_url(
                self.settings.get("source_url", ""), self.sha, self.repoPath, self.path
            )
            render["img_path"] = "export/" + self.part_info["name"] + ".png"

        elif render_method == "img":
            render["method_preference"] = "img"
            render["img_path"] = "export/" + self.part_info["name"] + ".png"
        else:
            # just put whatever the user dropped in as the render link
            # TODO should download this and package this image locally
            render["method_preference"] = "img"
            render["img_path"] = render_method

        part_manifest["render"] = render
        
        if export_method == "step":
            part_manifest["export"] = "export/" + self.part_info["name"] + ".step"
        elif export_method == "stl":
            part_manifest["export"] = "export/" + self.part_info["name"] + ".stl"

        manifest["parts"].append(part_manifest)

        return True

    def outOpenscad(self, render_method, export_method, manifest):
        Logger.info(f"Rendering OpenSCAD file: {self.name}")
        
        # Copy file to render queue input directory
        renderInputPath = self.abPath + "/renderQueue/openscad/in/" + self.name + ".scad"
        os.makedirs(os.path.dirname(renderInputPath), exist_ok=True)
        # Remove existing file if it exists (from previous failed run)
        if os.path.exists(renderInputPath):
            os.remove(renderInputPath)
        shutil.copyfile(self.path, renderInputPath)

        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Connect to render server via TCP socket
        host, port = get_mcad_socket_address(self.abPath)
        
        # Wait for server to be ready (try connecting a few times)
        max_retries = 20
        retry_interval = 0.5
        client_sock = None
        
        for attempt in range(max_retries):
            try:
                client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_sock.settimeout(2)
                client_sock.connect((host, port))
                client_sock.settimeout(self.RENDER_TIMEOUT_S)
                break
            except (ConnectionRefusedError, OSError):
                if client_sock:
                    client_sock.close()
                if attempt < max_retries - 1:
                    time.sleep(retry_interval)
                else:
                    self.last_error = (
                        f"Could not connect to OpenSCAD render server at {host}:{port} "
                        f"after {max_retries} attempts"
                    )
                    Logger.warn(self.last_error)
                    return False
        
        try:
            # Send render request
            request = create_request(
                "render",
                self.name,
                request_id=request_id,
                file_type="scad"
            )
            send_message(client_sock, request)
            Logger.info(f"Sent render request for {self.name} (timeout {self.RENDER_TIMEOUT_S}s)")
            
            # Wait for response
            response = receive_message(client_sock)
            client_sock.close()
            
            if not response:
                self.last_error = "No response received from OpenSCAD render server"
                Logger.warn(f"{self.name}: {self.last_error}")
                return False
            
            if response.get("status") != STATUS_SUCCESS:
                self.last_error = response.get("error", "Unknown error")
                Logger.warn(f"Render failed for {self.name}: {self.last_error}")
                return False
            
            Logger.info(f"Render completed successfully for {self.name}")
            
        except socket.timeout:
            self.last_error = f"Timeout after {self.RENDER_TIMEOUT_S}s waiting for OpenSCAD render"
            Logger.warn(f"{self.name}: {self.last_error}")
            return False
        except ConnectionRefusedError:
            self.last_error = f"Connection refused to OpenSCAD render server at {host}:{port}"
            Logger.warn(self.last_error)
            Logger.warn("Check container logs: docker-compose -f docker-compose-local.yaml logs freecad")
            return False
        except Exception as e:
            self.last_error = f"Error communicating with OpenSCAD render server: {e}"
            Logger.warn(f"{self.name}: {self.last_error}")
            Logger.warn(f"Check container logs: docker-compose -f docker-compose-local.yaml logs")
            return False

        # Copy output files to export directory
        try:
            exportFiles = os.listdir(self.abPath + "/renderQueue/openscad/out")
            for file in exportFiles:
                source_file = os.path.join(self.abPath + "/renderQueue/openscad/out", file)
                if os.path.isfile(source_file):
                    shutil.copy(source_file, self.repoPath + "/autobom/export")
                    os.remove(source_file)
        except Exception as e:
            self.last_error = f"Error copying OpenSCAD export files: {e}"
            Logger.warn(f"{self.name}: {self.last_error}")
            return False

        # update manifest
        part_manifest = copy.deepcopy(self.part_info)

        render = {"method_preference": "", "img_path": "", "3d_path": ""}

        if render_method == "img":
            render["method_preference"] = "img"
            render["img_path"] = "export/" + self.part_info["name"] + ".png"
        else:
            # just put whatever the user dropped in as the render link
            render["method_preference"] = "img"
            render["img_path"] = render_method

        part_manifest["render"] = render
        
        if export_method == "stl":
            part_manifest["export"] = "export/" + self.part_info["name"] + ".stl"

        manifest["parts"].append(part_manifest)

        return True