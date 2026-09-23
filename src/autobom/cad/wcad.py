# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

import os, time, copy, shutil, stat, socket, uuid

from ..base.logger import Logger
from ..base.socket_protocol import (
    get_wcad_socket_address,
    send_message, receive_message,
    create_request, STATUS_SUCCESS
)


class WCAD():

    RENDER_TIMEOUT_S = 1800

    def __init__(self, part_info, settings, sha, repoPath, abPath):
        self.part_info = part_info
        self.settings = settings
        self.path = None  # path to the .yml / .yaml
        self.sha = sha
        self.name = self.part_info["name"]
        self.repoPath = repoPath
        self.abPath = abPath
        self.last_error = None

    def del_rw(self, action, name, exc):
        os.chmod(name, stat.S_IWRITE)
        os.remove(name)

    def out(self, manifest):
        """Export/render this part. Returns True on success, False on failure."""
        self.last_error = None
        if not self.path or not os.path.isfile(self.path):
            self.last_error = f"No WireViz YAML found for {self.name}"
            Logger.warn(self.last_error)
            return False
        if self.outWireviz(manifest):
            Logger.info(f"Exported and rendered {self.name}")
            return True
        Logger.warn(f"Failed to export or render {self.name}: {self.last_error}")
        return False

    def outWireviz(self, manifest):
        Logger.info(f"Rendering WireViz harness: {self.name}")
        Logger.info(f"Source {self.path}")

        renderInputPath = os.path.join(self.abPath, "renderQueue", "wireviz", "in", self.name)
        os.makedirs(os.path.dirname(renderInputPath), exist_ok=True)
        if os.path.exists(renderInputPath):
            shutil.rmtree(renderInputPath)

        src_dir = os.path.dirname(self.path)
        shutil.copytree(src_dir, renderInputPath)

        # Connector photos are typically ../img relative to the YAML.
        img_dir = os.path.join(os.path.dirname(src_dir), "img")
        if os.path.isdir(img_dir):
            dest_img = os.path.join(os.path.dirname(renderInputPath), "img")
            if os.path.isdir(dest_img):
                shutil.rmtree(dest_img)
            shutil.copytree(img_dir, dest_img)

        request_id = str(uuid.uuid4())
        host, port = get_wcad_socket_address(self.abPath)

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
                        f"Could not connect to WireViz render server at {host}:{port} "
                        f"after {max_retries} attempts (is docker-compose up?)"
                    )
                    Logger.warn(self.last_error)
                    return False

        try:
            request = create_request("render", self.name, request_id=request_id)
            send_message(client_sock, request)
            Logger.info(f"Sent render request for {self.name} (timeout {self.RENDER_TIMEOUT_S}s)")
            response = receive_message(client_sock)
            client_sock.close()

            if not response:
                self.last_error = "No response received from WireViz render server"
                Logger.warn(f"{self.name}: {self.last_error}")
                return False

            if response.get("status") != STATUS_SUCCESS:
                self.last_error = response.get("error", "Unknown error")
                Logger.warn(f"Render failed for {self.name}: {self.last_error}")
                return False

            Logger.info(f"Render completed successfully for {self.name}")

        except socket.timeout:
            self.last_error = f"Timeout after {self.RENDER_TIMEOUT_S}s waiting for WireViz render"
            Logger.warn(f"{self.name}: {self.last_error}")
            return False
        except ConnectionRefusedError:
            self.last_error = f"Connection refused to WireViz render server at {host}:{port}"
            Logger.warn(self.last_error)
            return False
        except Exception as e:
            self.last_error = f"Error communicating with WireViz render server: {e}"
            Logger.warn(f"{self.name}: {self.last_error}")
            return False

        try:
            export_dir = os.path.join(self.abPath, "renderQueue", "wireviz", "out", self.name)
            dest_dir = os.path.join(self.repoPath, "autobom", "export", self.name)
            if os.path.isdir(export_dir):
                if os.path.exists(dest_dir):
                    shutil.rmtree(dest_dir)
                shutil.copytree(export_dir, dest_dir)
                png_src = os.path.join(dest_dir, self.name + ".png")
                if os.path.isfile(png_src):
                    shutil.copy2(png_src, os.path.join(self.repoPath, "autobom", "export", self.name + ".png"))
                try:
                    shutil.rmtree(export_dir, onerror=self.del_rw)
                except Exception:
                    pass
            else:
                self.last_error = f"WireViz output directory missing: {export_dir}"
                Logger.warn(self.last_error)
                return False
        except Exception as e:
            self.last_error = f"Error copying WireViz export files: {e}"
            Logger.warn(f"{self.name}: {self.last_error}")
            return False

        export_method = self.settings.get("wcad", {}).get("export", "svg")
        if "export" in self.part_info:
            export_method = self.part_info["export"]

        part_manifest = copy.deepcopy(self.part_info)
        part_manifest["render"] = {
            "method_preference": "img",
            "img_path": "export/" + self.name + ".png",
            "3d_path": "",
            "kicad_path": "",
        }
        if export_method == "png":
            part_manifest["export"] = "export/" + self.name + "/" + self.name + ".png"
        else:
            part_manifest["export"] = "export/" + self.name + "/" + self.name + ".svg"

        manifest["parts"].append(part_manifest)
        return True
