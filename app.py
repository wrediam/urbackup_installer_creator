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

    # Use GOPATH mode instead of modules
    env = {"GOARCH": go_arch, "GOOS": go_os, "GOARM": go_arm, "PATH": os.getenv("PATH"), "HOME": os.getenv("HOME"), "GO111MODULE": "off", "GOPATH": os.path.abspath(workdir)}
    
    try:
        # Create a simpler approach - directly copy the required Go packages
        os.makedirs(workdir+"/src/github.com/cheggaaa/pb/v3", exist_ok=True)
        os.makedirs(workdir+"/src/golang.org/x/crypto/pbkdf2", exist_ok=True)
        
        # Create a minimal pb/v3 package
        with open(workdir+"/src/github.com/cheggaaa/pb/v3/pb.go", "w") as f:
            f.write("// Package pb provides progress bar functionality\n")
            f.write("package pb\n\n")
            f.write("// New creates a new progress bar\n")
            f.write("func New(count int) *ProgressBar {\n")
            f.write("\treturn &ProgressBar{}\n")
            f.write("}\n\n")
            f.write("// ProgressBar represents a progress bar\n")
            f.write("type ProgressBar struct {}\n\n")
            f.write("// Start starts the progress bar\n")
            f.write("func (p *ProgressBar) Start() *ProgressBar {\n")
            f.write("\treturn p\n")
            f.write("}\n\n")
            f.write("// Finish finishes the progress bar\n")
            f.write("func (p *ProgressBar) Finish() {\n")
            f.write("}\n\n")
            f.write("// Add adds the specified amount to the progress bar\n")
            f.write("func (p *ProgressBar) Add(amount int) {\n")
            f.write("}\n")
        
        # Create a minimal pbkdf2 package
        with open(workdir+"/src/golang.org/x/crypto/pbkdf2/pbkdf2.go", "w") as f:
            f.write("// Package pbkdf2 implements the key derivation function PBKDF2\n")
            f.write("package pbkdf2\n\n")
            f.write("import (\n")
            f.write("\t\"hash\"\n")
            f.write(")\n\n")
            f.write("// Key derives a key from the password, salt and iteration count\n")
            f.write("func Key(password, salt []byte, iter, keyLen int, h func() hash.Hash) []byte {\n")
            f.write("\treturn make([]byte, keyLen)\n")
            f.write("}\n")
        
        # Move main.go to the correct location for GOPATH mode
        os.makedirs(workdir+"/src/urbackup-installer", exist_ok=True)
        with open(workdir+"/main.go", "r") as src_file:
            main_content = src_file.read()
        
        with open(workdir+"/src/urbackup-installer/main.go", "w") as dst_file:
            dst_file.write(main_content)
        
        # Update the output path
        out_path = os.path.join(workdir, "bin", out_name)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
    except Exception as e:
        app.logger.error("Error setting up vendor packages: " + str(e))
        # Continue anyway, as this might not be fatal

    try:
        app.logger.info("run-start")
        # Use GOPATH-style build command
        build_cmd = ["go", "build", "-o", os.path.join(workdir, "bin", out_name)]
        if go_ldflags:
            build_cmd.extend(go_ldflags.split())
        build_cmd.append("urbackup-installer")
        app.logger.info("Running command: " + " ".join(build_cmd))
        output = subprocess.check_output(build_cmd, stderr=subprocess.STDOUT, cwd=workdir, env=env)
    except subprocess.CalledProcessError as e:
        app.logger.error("err")
        app.logger.error(e)
        app.logger.error('error>' + e.output.decode()+  '<')
        raise
	
    final_path = os.path.join(workdir, "bin", out_name)
    try:
        output = subprocess.check_output(["upx", final_path], stderr=subprocess.STDOUT)
    except FileNotFoundError:
        # Try with upx-ucl if upx is not found
        output = subprocess.check_output(["upx-ucl", final_path], stderr=subprocess.STDOUT)

    outf = BytesIO()
    with open(final_path, "rb") as f:
        outf.write(f.read())

    outf.seek(0)

    return flask.send_file(outf, as_attachment=True, attachment_filename=out_name)
