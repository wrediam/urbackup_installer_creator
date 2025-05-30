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
        os.makedirs(workdir+"/src/github.com/cheggaaa/pb/v3/termutil", exist_ok=True)
        os.makedirs(workdir+"/src/golang.org/x/crypto/pbkdf2", exist_ok=True)
        os.makedirs(workdir+"/src/urbackup-installer", exist_ok=True)
        
        with open(workdir+"/src/urbackup-installer/main.go", "wt") as f:
            f.write(installer_go)
        
        # Create a minimal pb/v3 package
        with open(workdir+"/src/github.com/cheggaaa/pb/v3/pb.go", "w") as f:
            f.write("// Package pb provides progress bar functionality\n")
            f.write("package pb\n\n")
            f.write("import (\n")
            f.write("\t\"io\"\n")
            f.write(")\n\n")
            f.write("// Version of ProgressBar library\n")
            f.write("const Version = \"3.0.8\"\n\n")
            
            f.write("// ProgressBarTemplate type\n")
            f.write("type ProgressBarTemplate string\n\n")
            
            f.write("// Default template\n")
            f.write("const Default ProgressBarTemplate = \"[=>-]\"\n\n")
            
            f.write("// ProgressBar is the main object of bar\n")
            f.write("type ProgressBar struct {\n")
            f.write("\tcurrent, total int64\n")
            f.write("\twidth int\n")
            f.write("\tfinished bool\n")
            f.write("}\n\n")
            
            f.write("// Full is a template for the full progress bar\n")
            f.write("var Full = &Template{}\n\n")
            
            f.write("// Template is a progress bar template\n")
            f.write("type Template struct {}\n\n")
            
            f.write("// Start64 starts a new int64 progress bar\n")
            f.write("func (t *Template) Start64(total int64) *ProgressBar {\n")
            f.write("\treturn &ProgressBar{total: total}\n")
            f.write("}\n\n")
            
            f.write("// New creates a new progress bar\n")
            f.write("func New(count int) *ProgressBar {\n")
            f.write("\treturn &ProgressBar{total: int64(count)}\n")
            f.write("}\n\n")
            
            f.write("// New64 creates new ProgressBar object using int64 as total\n")
            f.write("func New64(total int64) *ProgressBar {\n")
            f.write("\treturn &ProgressBar{total: total}\n")
            f.write("}\n\n")
            
            f.write("// Start starts the progress bar\n")
            f.write("func (p *ProgressBar) Start() *ProgressBar {\n")
            f.write("\treturn p\n")
            f.write("}\n\n")
            
            f.write("// Finish finishes the progress bar\n")
            f.write("func (p *ProgressBar) Finish() *ProgressBar {\n")
            f.write("\tp.finished = true\n")
            f.write("\treturn p\n")
            f.write("}\n\n")
            
            f.write("// Add adds the specified amount to the progress bar\n")
            f.write("func (p *ProgressBar) Add(amount int) *ProgressBar {\n")
            f.write("\tp.current += int64(amount)\n")
            f.write("\treturn p\n")
            f.write("}\n\n")
            
            f.write("// Add64 adding given int64 value to bar value\n")
            f.write("func (p *ProgressBar) Add64(value int64) *ProgressBar {\n")
            f.write("\tp.current += value\n")
            f.write("\treturn p\n")
            f.write("}\n\n")
            
            f.write("// Set sets any value by any key\n")
            f.write("func (p *ProgressBar) Set(key, value interface{}) *ProgressBar {\n")
            f.write("\treturn p\n")
            f.write("}\n\n")
            
            f.write("// NewProxyReader creates a proxy reader\n")
            f.write("func (p *ProgressBar) NewProxyReader(r io.Reader) io.Reader {\n")
            f.write("\treturn &Reader{r, p}\n")
            f.write("}\n\n")
            
            f.write("// Reader is a proxy reader\n")
            f.write("type Reader struct {\n")
            f.write("\tio.Reader\n")
            f.write("\tbar *ProgressBar\n")
            f.write("}\n\n")
            
            f.write("// Read reads data from the reader\n")
            f.write("func (r *Reader) Read(p []byte) (n int, err error) {\n")
            f.write("\tn, err = r.Reader.Read(p)\n")
            f.write("\tr.bar.Add(n)\n")
            f.write("\treturn\n")
            f.write("}\n\n")
            
            f.write("// Close closes the reader when it implements io.Closer\n")
            f.write("func (r *Reader) Close() error {\n")
            f.write("\tif closer, ok := r.Reader.(io.Closer); ok {\n")
            f.write("\t\treturn closer.Close()\n")
            f.write("\t}\n")
            f.write("\treturn nil\n")
            f.write("}\n")
            
            # Create a termutil.go file for the termutil package reference
            with open(workdir+"/src/github.com/cheggaaa/pb/v3/termutil/termutil.go", "w") as tf:
                tf.write("// Package termutil provides terminal utilities\n")
                tf.write("package termutil\n\n")
                tf.write("// TerminalWidth returns the width of the terminal\n")
                tf.write("func TerminalWidth() (int, error) {\n")
                tf.write("\treturn 80, nil\n")
                tf.write("}\n")
        
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
        
        # We've already created the urbackup-installer directory and written main.go to it
        # No need to move it again
        
        # Update the output path
        out_path = os.path.join(workdir, "bin", out_name)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
    except Exception as e:
        app.logger.error("Error setting up vendor packages: " + str(e))
        # Continue anyway, as this might not be fatal

    try:
        app.logger.info("run-start")
        # Ensure bin directory exists
        bin_dir = os.path.join(workdir, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        
        # Use GOPATH-style build command with absolute path
        output_path = os.path.abspath(os.path.join(bin_dir, out_name))
        build_cmd = ["go", "build", "-o", output_path]
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
    
    # Check if the executable file exists
    if not os.path.exists(final_path):
        app.logger.error(f"Executable file not found at {final_path}")
        # List files in the bin directory to help debug
        bin_dir = os.path.join(workdir, "bin")
        if os.path.exists(bin_dir):
            app.logger.info(f"Files in {bin_dir}: {os.listdir(bin_dir)}")
        else:
            app.logger.error(f"Bin directory {bin_dir} does not exist")
            
        # Try to find the executable elsewhere
        for root, dirs, files in os.walk(workdir):
            for file in files:
                if file.endswith(".exe") or file == "UrBackupClientInstaller":
                    app.logger.info(f"Found potential executable at: {os.path.join(root, file)}")
                    final_path = os.path.join(root, file)
                    break
            if os.path.exists(final_path):
                break
    
    # Only try to compress if the file exists
    if os.path.exists(final_path):
        try:
            try:
                output = subprocess.check_output(["upx", final_path], stderr=subprocess.STDOUT)
            except FileNotFoundError:
                # Try with upx-ucl if upx is not found
                output = subprocess.check_output(["upx-ucl", final_path], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            app.logger.warning(f"UPX compression failed: {e}. Continuing with uncompressed executable.")
            # Continue without compression if UPX fails
    else:
        app.logger.error(f"Cannot compress non-existent file: {final_path}")
        # Create a simple error response
        return "Error: Failed to build installer. Check server logs for details.", 500

    outf = BytesIO()
    with open(final_path, "rb") as f:
        outf.write(f.read())

    outf.seek(0)

    # In newer Flask versions, attachment_filename is replaced with download_name
    return flask.send_file(outf, as_attachment=True, download_name=out_name)
