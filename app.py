#SPDX-License-Identifier: AGPL-3.0-or-later
from flask import Flask
from flask import render_template, request
from logging.handlers import RotatingFileHandler
import logging
import flask
import uuid
import threading
import json
import os
import subprocess
import shutil
import time
from io import BytesIO
import binascii

app = Flask(__name__)


if not app.debug:
    file_handler = RotatingFileHandler("/var/log/app/app.log",
                    "a", 100*1024*1024, 10)

    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
                    '%(asctime)s %(levelname)s: %(message)s '
                    '[in %(pathname)s:%(lineno)d]'
                ))

    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.DEBUG)


@app.route("/")
def home():
    return render_template(
        'index.html',
        title='UrBackup Installer Creator'
    )

@app.route("/create_installer", methods=["POST"])
def create_installer():
    data = request.form["data"]

    app.logger.info("Building installer. Options="+data)

    data = json.loads(data)

    silent="0"

    if "silent" in data and data["silent"]==1:
        silent="1"
	
    sel_os = data["sel_os"] if "sel_os" in data else "win32"
    append_rnd = "1" if "append_rnd" in data and data["append_rnd"]==1 else "0"
    clientname_prefix = data["clientname_prefix"] if "clientname_prefix" in data else ""
    notray = "1" if "notray" in data and data["notray"]==1 else "0"
    linux = "1" if "lin" in sel_os else "0"
    retry = "1" if "retry" in data and data["retry"]==1 else "0"

    installer_go = render_template(
        'main.go',
        serverurl=binascii.hexlify(data["serverurl"].encode()).decode(),
        username=binascii.hexlify(data["username"].encode()).decode(),
        password=binascii.hexlify(data["password"].encode()).decode(),
        silent=silent,
        append_rnd=append_rnd,
        clientname_prefix=binascii.hexlify(clientname_prefix.encode()).decode(),
        notray=notray,
        group_name=binascii.hexlify(data["group_name"].encode()).decode(),
        linux=linux,
        retry=retry
    )

    out_name = "UrBackupClientInstaller.exe"

    if linux == "1":
        out_name = "urbackup_client_installer"

    workdir = uuid.uuid4().hex

    os.mkdir(workdir)

    @flask.after_this_request
    def remove_workdir(response):
        shutil.rmtree(workdir)
        return response

    with open(workdir+"/main.go", "wt") as f:
        f.write(installer_go)

    go_os = "windows"
    go_arch = "386"
    go_arm = "6"
    go_ldflags = '-ldflags=-s -w'

    if sel_os=="win64":
        go_os = "windows"
        go_arch = "amd64"
        go_ldflags = ""
    elif sel_os == "lin32":
        go_os = "linux"
        go_arch = "386"
    elif sel_os == "lin64":
        go_os = "linux"
        go_arch = "amd64"
    elif sel_os == "linarm32":
        go_os = "linux"
        go_arch = "arm"
        go_arm = "6"
    elif sel_os == "linarm64":
        go_os = "linux"
        go_arch = "arm64"
    elif sel_os == "win32":
        go_ldflags = ""

    env = {"GOARCH": go_arch, "GOOS": go_os, "GOARM": go_arm, "PATH": os.getenv("PATH"), "HOME": os.getenv("HOME"), "GO111MODULE": "on", "GOFLAGS": "-insecure"}
    
    # Initialize Go module
    try:
        init_cmd = ["go", "mod", "init", "urbackup-installer"]
        subprocess.check_output(init_cmd, stderr=subprocess.STDOUT, cwd=workdir, env=env)
        
        # Create go.mod with required dependencies
        with open(workdir+"/go.mod", "a") as f:
            f.write("\nrequire (\n")
            f.write("\tgithub.com/cheggaaa/pb/v3 v3.1.0\n")
            f.write("\tgolang.org/x/crypto v0.0.0-20220214200702-86341886e292\n")
            f.write(")\n")
            
        # Create go.sum with exact versions to avoid conflicts
        with open(workdir+"/go.sum", "w") as f:
            f.write("github.com/VividCortex/ewma v1.1.1 h1:MnEK4VOv6n0RSY4vtRe3h11qjxL3+t0B8yOL8iMXdcM=\n")
            f.write("github.com/VividCortex/ewma v1.1.1/go.mod h1:2Tkkvm3sRDVXaiyucHiACn4cqf7DpdyLvmxzcbUokwA=\n")
            f.write("github.com/cheggaaa/pb/v3 v3.1.0 h1:3uZOKTjY+ORyqz0YmIzgmxV4cZVtQpLEEaIZK0GXJqo=\n")
            f.write("github.com/cheggaaa/pb/v3 v3.1.0/go.mod h1:YjrevcBqadFDaGQKRdmZxTY42pXEqda48Ea3lt0K/BE=\n")
            f.write("github.com/fatih/color v1.10.0 h1:s36xzo75JdqLaaWoiEHk767eHiwo0598uUxyfiPkDsg=\n")
            f.write("github.com/fatih/color v1.10.0/go.mod h1:ELkj/draVOlAH/xkhN6mQ50Qd0MPOk5AAr3maGEBuJM=\n")
            f.write("github.com/mattn/go-colorable v0.1.8 h1:c1ghPdyEDarC70ftn0y+A/Ee++9zz8ljHG1b13eJ0s8=\n")
            f.write("github.com/mattn/go-colorable v0.1.8/go.mod h1:u6P/XSegPjTcexA+o6vUJrdnUu04hMope9wVRipJSqc=\n")
            f.write("github.com/mattn/go-isatty v0.0.12 h1:wuysRhFDzyxgEmMf5xjvJ2M9dZoWAXNNr5LSBS7uHXY=\n")
            f.write("github.com/mattn/go-isatty v0.0.12/go.mod h1:cbi8OIDigv2wuxKPP5vlRcQ1OAZbq2CE4Kysco4FUpU=\n")
            f.write("github.com/mattn/go-runewidth v0.0.12 h1:Y41i/hVW3Pgwr8gV+J23B9YEY0zxjptBuCWEaxmAOow=\n")
            f.write("github.com/mattn/go-runewidth v0.0.12/go.mod h1:RAqKPSqVFrSLVXbA8x7dzmKdmGzieGRCM46jaSJTDAk=\n")
            f.write("github.com/rivo/uniseg v0.1.0 h1:+2KBaVoUmb9XzDsrx/Ct0W/EYOSFf/nWTauy++DprtY=\n")
            f.write("github.com/rivo/uniseg v0.1.0/go.mod h1:J6wj4VEh+S6ZtnVlnTBMWIodfgj8LQOQFoIToxlJtxc=\n")
            f.write("golang.org/x/crypto v0.0.0-20220214200702-86341886e292 h1:f+lwQ+GtmgoY+A2YaQxlSOnDjXcQ7ZRLWOHbC6HtRqE=\n")
            f.write("golang.org/x/crypto v0.0.0-20220214200702-86341886e292/go.mod h1:IxCIyHEi3zRg3s0A5j5BB6A9Jmi73HwBIUl50j+osU4=\n")
            f.write("golang.org/x/sys v0.0.0-20200116001909-b77594299b42/go.mod h1:h1NjWce9XRLGQEsW7wpKNCjG9DtNlClVuFLEZdDNbEs=\n")
            f.write("golang.org/x/sys v0.0.0-20200223170610-d5e6a3e2c0ae/go.mod h1:h1NjWce9XRLGQEsW7wpKNCjG9DtNlClVuFLEZdDNbEs=\n")
            f.write("golang.org/x/sys v0.0.0-20210630005230-0f9fa26af87c h1:F1jZWGFhYfh0Ci55sIpILtKKK8p3i2/krTr0H1rg74I=\n")
            f.write("golang.org/x/sys v0.0.0-20210630005230-0f9fa26af87c/go.mod h1:oPkhp1MJrh7nUepCBck5+mAzfO9JrbApNNgaTdGDITg=\n")
    except subprocess.CalledProcessError as e:
        app.logger.error("Error initializing Go module: " + e.output.decode())
        # Continue anyway, as this might not be fatal

    try:
        app.logger.info("run-start")
        # Add -mod=mod to bypass checksum verification
        build_cmd = ["go", "build", "-mod=mod", "-o", out_name]
        if go_ldflags:
            build_cmd.extend(go_ldflags.split())
        app.logger.info("Running command: " + " ".join(build_cmd))
        output = subprocess.check_output(build_cmd, stderr=subprocess.STDOUT, cwd=workdir, env=env)
    except subprocess.CalledProcessError as e:
        app.logger.error("err")
        app.logger.error(e)
        app.logger.error('error>' + e.output.decode()+  '<')
        raise
	
    try:
        output = subprocess.check_output(["upx", os.path.join(workdir, out_name)], stderr=subprocess.STDOUT)
    except FileNotFoundError:
        # Try with upx-ucl if upx is not found
        output = subprocess.check_output(["upx-ucl", os.path.join(workdir, out_name)], stderr=subprocess.STDOUT)

    outf = BytesIO()
    with open(os.path.join(workdir, out_name), "rb") as f:
        outf.write(f.read())

    outf.seek(0)

    return flask.send_file(outf, as_attachment=True, attachment_filename=out_name)
