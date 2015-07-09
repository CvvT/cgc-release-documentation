#!/usr/bin/env python

import argparse
import glob
import os
import hashlib
import json
import subprocess
import sys
import re

def verify(csid, pov, files):
    """
    pre packaging verification is done here
    """
    # check csid
    if not re.match(r"^[0-9a-f]{8}$", csid):
        raise NameError("CSID is not in the correct format")

    expected_num_cbs = int(csid[-2:], 16)
    if expected_num_cbs < 1:
        raise NameError("CSID is not in the correct format")

    # check number of replacement binaries
    num_cbs = len(files)
    if num_cbs != expected_num_cbs:
        raise ValueError("Incorrect numer of replacement binaries: expected %d, got %d" % (expected_num_cbs, num_cbs))

    # check replacement binary naming and format
    files.sort()
    for index, f in enumerate(files, start=1):
        expected_name = "RB_%s_%02x" % (csid, index)
        if f != expected_name:
            raise NameError("replacement binary incorrectly named.  Expected %s, got %s" % (expected_name, f))
        try:
            cmd = ['cgcef_verify', f]
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as cpe:
            raise IOError("Error: %s returned %d" % (cpe.cmd, cpe.returncode))

    # check PoV naming and format
    expected_name = "POV_%s.xml" % csid
    if pov != expected_name:
        raise NameError("Error:  PoV incorrectly named.  Expected %s, got %s" % (expected_name, pov))
    try:
        cmd = ['poll-validate', pov]
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as cpe:
        raise IOError("Error: %s returned %d" % (cpe.cmd, cpe.returncode))
    
def package(csid, pov, files, passphrase):
    """
    Packaging method for building a solution for submission. Both
    companion file and encrypted solution package are created
    """
    pkg_name = csid + ".ar"
    
    # create the archive
    try:
        cmd = ["ar", "crSD", pkg_name, pov] + files
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as cpe:
        raise IOError("Error: %s returned %d" % (cpe.cmd, cpe.returncode))

    # compute the archive hash
    m = hashlib.sha256()
    m.update(open(pkg_name, "rb").read())
    hashval = m.hexdigest()
    
    # setup names
    base_name = csid + "_" + hashval
    pkg_name_s = base_name + ".ar.enc"
    commitment_name = base_name + ".txt"

    # encrypt solution package
    try:
        cmd = ["openssl", "aes-256-cbc", "-pass", "pass:%s" % passphrase, 
                "-in", pkg_name, "-out", pkg_name_s]
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as cpe:
        raise IOError("Error: %s return %d" % (cpe.cmd, cpe.returncode))
        
    # generate a commitment file
    open(commitment_name, "w").close()

    return (commitment_name, pkg_name_s)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--creds", 
                        help="path to CGC credentials JSON file", 
                        type=str, required=True)

    parser.add_argument("-n", "--csid", 
                        help="Challenge Set ID", required=True)

    parser.add_argument("-p", "--pov", 
                        help="Proof of Vulnerability file", required=True)

    parser.add_argument("-f", "--files", nargs="+", required=True,
                        help="List of replacement CBs")

    args = parser.parse_args()

    if not os.path.exists(args.creds):
        sys.exit("Error: cannot find creds file '%s'" % args.creds)

    if not os.path.exists(args.pov):
        sys.exit("Error: cannot find PoV file '%s'" % args.pov)

    for f in args.files:
        if not os.path.exists(f):
            sys.exit("Error:  cannot find replacement CB '%s'" % f)

    # verify components and naming
    verify(args.csid, args.pov, args.files)

    # load credentials
    creds = json.loads(open(args.creds, "r").read())

    # package solution and generate commitment
    (commitment_file, solution_file) = package(args.csid, args.pov, args.files, creds['cqe_encryption_key'])
    print "Commitment file:   " + commitment_file
    print "Encrypted solution package: " + solution_file
    
