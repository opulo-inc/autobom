# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

import os, time, copy, shutil, stat, socket, uuid

from ..base.logger import Logger
from ..base.socket_protocol import (
    get_ecad_socket_address,
    send_message, receive_message,
    create_request, STATUS_SUCCESS, STATUS_FAILURE
)


class ECAD():

    def __init__(self, part_info, settings, sha, repoPath, abPath):

        self.part_info = part_info
        self.settings = settings
        self.path = None
        self.sha = sha
        self.name = self.part_info["name"]
        self.repoPath = repoPath
        self.abPath = abPath

    def del_rw(self, action, name, exc):
        os.chmod(name, stat.S_IWRITE)
        os.remove(name)

    def out(self, manifest):
        """Export/render this part. Returns True on success, False on failure."""
        #using default settings, but allowing part-specific to override
        render_method = self.settings["ecad"]["render"]
        if "render" in self.part_info:
            render_method = self.part_info["render"]

        export_method = self.settings["ecad"]["export"]
        if "export" in self.part_info:
            export_method = self.part_info["export"]

        if os.path.isfile(self.path + "/" + self.name + ".kicad_pro"):
            if self.outKicad(render_method, export_method, manifest):
                Logger.info(f"Exported and rendered {self.part_info['name']}")
                return True
            Logger.warn(f"Failed to export or render {self.part_info['name']}")
            return False

        Logger.warn(f"No supported KiCAD project found for {self.part_info['name']}")
        return False


    def outKicad(self, render_method, export_method, manifest):
        Logger.info(f"Rendering KiCAD project: {self.name}")
    
        # Copy project directory to render queue input directory
        renderInputPath = self.abPath + "/renderQueue/kicad/in/" + self.name
        os.makedirs(os.path.dirname(renderInputPath), exist_ok=True)
        # Remove existing directory if it exists (from previous failed run)
        if os.path.exists(renderInputPath):
            shutil.rmtree(renderInputPath)
        shutil.copytree(self.path, renderInputPath)

        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Connect to render server via TCP socket
        host, port = get_ecad_socket_address(self.abPath)
        
        # Wait for server to be ready (try connecting a few times)
        max_retries = 20
        retry_interval = 0.5
        client_sock = None
        
        for attempt in range(max_retries):
            try:
                client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_sock.settimeout(2)
                client_sock.connect((host, port))
                client_sock.settimeout(120)  # Set longer timeout for actual communication
                break
            except (ConnectionRefusedError, OSError):
                if client_sock:
                    client_sock.close()
                if attempt < max_retries - 1:
                    time.sleep(retry_interval)
                else:
                    Logger.warn(f"Could not connect to render server at {host}:{port} after {max_retries} attempts.")
                    Logger.warn("Make sure Docker containers are running: docker-compose up -d")
                    return False
        
        try:
            
            # Send render request
            request = create_request(
                "render",
                self.name,
                request_id=request_id
            )
            send_message(client_sock, request)
            Logger.info(f"Sent render request for {self.name}")
            
            # Wait for response
            response = receive_message(client_sock)
            client_sock.close()
            
            if not response:
                Logger.warn(f"No response received for {self.name}")
                return False
            
            if response.get("status") != STATUS_SUCCESS:
                error_msg = response.get("error", "Unknown error")
                Logger.warn(f"Render failed for {self.name}: {error_msg}")
                return False
            
            Logger.info(f"Render completed successfully for {self.name}")
            
        except socket.timeout:
            Logger.warn(f"Timeout waiting for render response for {self.name}")
            return False
        except ConnectionRefusedError:
            Logger.warn(f"Connection refused to render server at {host}:{port}.")
            Logger.warn("The server isn't accepting connections.")
            Logger.warn("Check container logs: docker-compose -f docker-compose-local.yaml logs kicad")
            return False
        except Exception as e:
            Logger.warn(f"Error communicating with render server for {self.name}: {str(e)}")
            Logger.warn(f"Check container logs: docker-compose -f docker-compose-local.yaml logs")
            return False

        # Copy output files to export directory
        try:
            exportDir = self.abPath + "/renderQueue/kicad/out/" + self.name
            if os.path.exists(exportDir):
                shutil.copytree(exportDir, self.repoPath + "/autobom/export/" + self.name)
                # Clean up output directory
                try:
                    shutil.rmtree(exportDir, onerror=self.del_rw)
                except:
                    pass
        except Exception as e:
            Logger.warn(f"Error copying export files for {self.name}: {str(e)}")
            return False

        # update manifest
        part_manifest = copy.deepcopy(self.part_info)

        render = {"method_preference": "", "img_path": "", "3d_path": ""}

        if render_method == "src":
            # this is easy, it's just pulling the github link! no sweat!
            repo = self.settings['source_url']

            ghlink = repo + "/blob/" + self.sha + "/" + self.path

            # correctly formatted gh link for reference
            # https://github.com/opulo-inc/lumenpnp/blob/be58b3eeba5aecb69e166f0e397c5b0ebc95fa33/pnp/cad/FDM/y-gantry.FCStd
            
            render["method_preference"] = "3d"
            render["3d_path"] = ghlink
            render["img_path"] = "export/" + self.part_info["name"] + "/" + self.part_info["name"] + "-top.png"

        elif render_method == "img":
            render["method_preference"] = "img"
            render["img_path"] = "export/" + self.part_info["name"] + "/" + self.part_info["name"] + "-top.png"
        else:
            # just put whatever the user dropped in as the render link
            render["method_preference"] = "img"
            render["img_path"] = render_method

        part_manifest["render"] = render
        
        if export_method == "step":
            part_manifest["export"] = "export/" + self.part_info["name"] + ".step"
        elif export_method == "stl":
            part_manifest["export"] = "export/" + self.part_info["name"] + ".step"

        manifest["parts"].append(part_manifest)

        return True
        