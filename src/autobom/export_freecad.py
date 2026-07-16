# Copyright (c) 2024 Opulo, Inc
# Published under the Mozilla Public License
# Full text available at: https://www.mozilla.org/en-US/MPL/

"""
Utility script to export STEP files from all FreeCAD files in a directory tree.
"""

import os
import sys
import shutil
import logging
from pathlib import Path

from .base.logger import Logger
from .base.socket_protocol import (
    get_mcad_socket_address,
    send_message, receive_message,
    create_request, STATUS_SUCCESS, STATUS_FAILURE
)
import socket
import time
import uuid


def find_freecad_files(root_dir):
    """Find all .fcstd files recursively in the directory tree."""
    freecad_files = []
    for root, dirs, files in os.walk(root_dir):
        # Skip autobom directory
        if 'autobom' in dirs:
            dirs.remove('autobom')
        for file in files:
            if file.lower().endswith('.fcstd'):
                full_path = os.path.join(root, file)
                freecad_files.append(full_path)
    return freecad_files


def export_step_via_socket(file_path, ab_path, export_dir):
    """Export a STEP file from a FreeCAD file using the render server."""
    file_name = Path(file_path).stem
    
    # Copy file to render queue input directory
    render_input_dir = os.path.join(ab_path, "renderQueue", "freecad", "in")
    render_input_path = os.path.join(render_input_dir, file_name + ".FCStd")
    
    # Ensure directory exists
    os.makedirs(render_input_dir, exist_ok=True)
    
    # Verify source file exists
    if not os.path.exists(file_path):
        Logger.warn(f"Source file does not exist: {file_path}")
        return False
    
    # Remove existing file if it exists
    if os.path.exists(render_input_path):
        os.remove(render_input_path)
    
    # Copy file
    try:
        shutil.copyfile(file_path, render_input_path)
        Logger.info(f"Copied {file_path} to {render_input_path}")
        
        # Verify copy succeeded
        if not os.path.exists(render_input_path):
            Logger.warn(f"File copy failed - destination does not exist: {render_input_path}")
            return False
    except Exception as e:
        Logger.warn(f"Error copying file: {e}")
        return False
    
    # Generate unique request ID
    request_id = str(uuid.uuid4())
    
    # Connect to render server via TCP socket
    host, port = get_mcad_socket_address(ab_path)
    
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
            file_name,
            request_id=request_id,
            file_type="fcstd"
        )
        send_message(client_sock, request)
        Logger.info(f"Sent render request for {file_name}")
        
        # Wait for response
        response = receive_message(client_sock)
        client_sock.close()
        
        if not response:
            Logger.warn(f"No response received for {file_name}")
            return False
        
        if response.get("status") != STATUS_SUCCESS:
            error_msg = response.get("error", "Unknown error")
            Logger.warn(f"Render failed for {file_name}: {error_msg}")
            return False
        
        Logger.info(f"Render completed successfully for {file_name}")
        
    except socket.timeout:
        Logger.warn(f"Timeout waiting for render response for {file_name}")
        return False
    except ConnectionRefusedError:
        Logger.warn(f"Connection refused to render server at {host}:{port}.")
        Logger.warn("The server isn't accepting connections.")
        Logger.warn("Check container logs: docker-compose -f docker-compose-local.yaml logs freecad")
        return False
    except Exception as e:
        Logger.warn(f"Error communicating with render server for {file_name}: {str(e)}")
        Logger.warn(f"Check container logs: docker-compose -f docker-compose-local.yaml logs")
        return False
    
    # Copy output files to export directory
    try:
        export_files = os.listdir(os.path.join(ab_path, "renderQueue", "freecad", "out"))
        for file in export_files:
            source_file = os.path.join(ab_path, "renderQueue", "freecad", "out", file)
            if os.path.isfile(source_file):
                # Only copy STEP files
                if file.lower().endswith('.step'):
                    dest_file = os.path.join(export_dir, file)
                    shutil.copy(source_file, dest_file)
                    Logger.info(f"Exported {file} to {dest_file}")
                os.remove(source_file)
        return True
    except Exception as e:
        Logger.warn(f"Error copying export files for {file_name}: {str(e)}")
        return False


def main():
    """Main entry point for export-freecad utility."""
    logging.basicConfig(level=logging.DEBUG)
    
    # Get autobom path - try environment variable first, then auto-detect
    ab_path = os.environ.get('GITHUB_ACTION_PATH')
    
    if not ab_path:
        # Auto-detect: find the autobom repo
        # Strategy 1: Check where the package is installed (most reliable)
        # When running via `uv run --project /path/to/autobom`, 
        # the package location tells us where the project is
        script_file = os.path.abspath(__file__)
        # __file__ is src/autobom/export_freecad.py
        # Go up: src/autobom -> src -> repo root
        potential_repo = os.path.dirname(os.path.dirname(os.path.dirname(script_file)))
        if os.path.exists(os.path.join(potential_repo, "renderQueue")) and os.path.exists(os.path.join(potential_repo, "pyproject.toml")):
            ab_path = potential_repo
        
        # Strategy 2: Check if we're running from within the autobom repo
        # Look for both renderQueue AND pyproject.toml to ensure it's the actual repo
        if not ab_path:
            cwd = os.getcwd()
            check_path = cwd
            for _ in range(5):  # Check up to 5 levels up
                if (os.path.exists(os.path.join(check_path, "renderQueue")) and 
                    os.path.exists(os.path.join(check_path, "pyproject.toml"))):
                    ab_path = check_path
                    break
                parent = os.path.dirname(check_path)
                if parent == check_path:  # Reached root
                    break
                check_path = parent
        
        # Strategy 3: Check common location
        if not ab_path:
            common_path = os.path.expanduser("~/autobom")
            if os.path.exists(os.path.join(common_path, "renderQueue")) and os.path.exists(os.path.join(common_path, "pyproject.toml")):
                ab_path = common_path
        
        if not ab_path:
            Logger.warn("Could not auto-detect autobom repository path.")
            Logger.warn("Please set GITHUB_ACTION_PATH environment variable:")
            Logger.warn("  GITHUB_ACTION_PATH=/path/to/autobom uv run --project /path/to/autobom export-freecad")
            return
    
    # Verify it exists and has renderQueue
    if not os.path.exists(ab_path):
        Logger.warn(f"AutoBOM path does not exist: {ab_path}")
        return
    
    render_queue = os.path.join(ab_path, "renderQueue")
    if not os.path.exists(render_queue):
        Logger.warn(f"renderQueue directory not found at {render_queue}")
        Logger.warn("Please ensure the autobom repository path is correct")
        return
    
    current_dir = os.getcwd()
    
    Logger.info(f"AutoBOM Path: {ab_path}")
    Logger.info(f"Current Directory: {current_dir}")
    
    # Create export directory
    export_dir = os.path.join(current_dir, "autobom", "export")
    os.makedirs(export_dir, exist_ok=True)
    
    # Find all FreeCAD files
    Logger.info("Searching for FreeCAD files...")
    freecad_files = find_freecad_files(current_dir)
    
    if not freecad_files:
        Logger.warn("No FreeCAD files found in current directory tree")
        return
    
    Logger.info(f"Found {len(freecad_files)} FreeCAD file(s)")
    
    # Export each file
    success_count = 0
    for file_path in freecad_files:
        Logger.info(f"Processing: {file_path}")
        if export_step_via_socket(file_path, ab_path, export_dir):
            success_count += 1
    
    Logger.info(f"Export complete: {success_count}/{len(freecad_files)} files exported successfully")


if __name__ == '__main__':
    main()
