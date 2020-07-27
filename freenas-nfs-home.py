#!/usr/bin/env python3

# This script is designed to create or delete a dataset for a home directory, with a quota, and one or more NFS
# shares with or without root squash as required.

# Support packages, be sure they're included as part of your Python environment.
import ipaddress
import sys
import getpass
import json
import requests

# Initial information This information can either be pre-set here if this script will be frequently used,
# or else leave the defaults to be prompted at execution time. For deletion, quota and NFS settings are ignored.

# FreeNAS Server name. NOTE: Must be IP address or match the DNS name under Network > Global Settings.
freenasserver = "freenas.example.org"

# Set whether to use HTTP or HTTPS to connect. HTTPS must use a signed certificate or Python will fail to connect.
serverscheme = "http"
# Username to login with, default is root in FreeNAS.
login = "root"

# Pool and parent dataset (e.g. /mnt/tank/home/). Subfolders allowed (e.g. /mnt/tank/groupa/home)
pool = "poolname"
parentdataset = "parentdataset"
# Quota to apply to the dataset, using the same format as the FreeNAS UI). Set to "0" to disable quota
quota = "0"

# NFS share subnet in CDIR notation. Multiple can be in one share separated with spaces. Single hosts are /32. To
# enable map_root, enter username to map root to, typically "root". Setting "none" will enable root_squash,
# the default behavior on FreeNAS NFS mounts.
nfsnetwork = ["127.0.0.1/32"]
nfsmaproot = ["none"]
nfscomment = ["Server A share"]


#  Uncomment and add as many additional shares as required for your environment.
# nfsnetwork.append("127.0.0.2/32 127.0.0.3/32")
# nfsmaproot.append("none")
# nfscomment.append("Server B share")

# ### DO NOT EDIT BELOW THIS LINE ###

# Build a table for text formatting
class BColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


# Print help if we don't get required arguments:
if len(sys.argv) != 3 or sys.argv[1] == "--help" or sys.argv[1] == "-h" or sys.argv[1] == "help":
    print("\n" + BColors.HEADER + BColors.BOLD + "FreeNAS shared home directory creation script\n" + BColors.ENDC)
    print(BColors.BOLD + "USAGE:" + BColors.ENDC + "freenas-nfs-home.py [mode] [username]\n")
    print(BColors.BOLD + "MODE:" + BColors.ENDC + " create or delete")
    print(BColors.BOLD + "USERNAME:" + BColors.ENDC + ": Name of the user to create a home directory at /mnt/" + pool +
          "/" + parentdataset + "/")
    print(BColors.WARNING + "If this is not the correct path, edit this script and adjust the pre-set variables, "
                            "or proceed to be prompted for them\n" + BColors.ENDC)
    exit(1)

# Set create/delete mode and new dataset from command line arguments.
mode = sys.argv[1]
newdataset = sys.argv[2]

# Die if we don't get the expected mode
while mode.lower() not in ['create', 'delete']:
    print(BColors.FAIL + "ERROR: Mode can only be \"create\" or \"delete\"" + BColors.ENDC)
    exit(1)

# Prompt for values if defaults are left in.
# Check for default hostname
if freenasserver == "freenas.example.org":
    print(BColors.WARNING + "WARNING: Default hosstname found." + BColors.ENDC)
    freenasserver = input("Please enter FreeNAS hostname: ")

# Set pool and home directory information
if pool == "poolname":
    print(BColors.WARNING + "WARNING: Default pool found!" + BColors.ENDC)
    pool = input("Enter pool name:")

if parentdataset == "parentdataset":
    print(BColors.WARNING + "WARNING: Default parent dataset found!" + BColors.ENDC)
    parentdataset = input("Enter parent dataset name:")

if nfsnetwork == "127.0.0.1/32" or nfscomment == "Server A share":
    print(BColors.WARNING + "WARNING: Default NFS share found!" + BColors.ENDC)
    del nfsnetwork
    nfsnetwork = [input("Please enter NFS client(s) in CDIR notation: ")]
    nfsmaproot = [input("Please enter 'Maproot User' username or 'none': ")]
    nfscomment = [input("Please enter NFS share description: ")]

# Validate NFS share IP addressing
# For one share:
if len(nfsnetwork) == 1:
    for block in nfsnetwork[0].split(" "):
        try:
            ipaddr = ipaddress.ip_network(block)
        except ValueError:
            print(BColors.FAIL + "ERROR: \"" + block + "\" is not a valid CDIR block." + BColors.ENDC)
            exit(1)

# For more than one share:
if len(nfsnetwork) > 1:
    i = 0
    while i < len(nfsnetwork):
        for block in nfsnetwork[i].split(" "):
            try:
                ipaddr = ipaddress.ip_network(block)
            except ValueError:
                print(BColors.FAIL + "ERROR: \"" + block + "\" is not a valid CDIR block." + BColors.ENDC)
                exit(1)
        i += 1

# Validate maproot user:
# For one share:
if len(nfsnetwork) == 1:
    if str.lower(nfsmaproot[0]) != "none":
        if not nfsmaproot[0].isalpha():
            print(BColors.FAIL + "ERROR: \"" + nfsmaproot[
                0] + "\" is not a valid username for Maproot User! Exiting." + BColors.ENDC)
            exit(1)

# For more than one share
if len(nfsnetwork) > 1:
    i = 0
    while i < len(nfsnetwork):
        if str.lower(nfsmaproot[i]) != "none":
            if not nfsmaproot[i].isalpha():
                print(BColors.FAIL + "ERROR: \"" + nfsmaproot[i] + "\" is not a valid username for Maproot User! "
                                                                   "Exiting." + BColors.ENDC)
                exit(1)

        i += 1

# Set server information
# Prompt for hostname if default is found
if freenasserver == "freenas.exmaple.org":
    print(BColors.WARNING + "WARNING: Default FreeNAS hostname found!" + BColors.ENDC)
    freenasserver = input("Enter FreeNAS Hostname: ")

# Check for correct URI scheme, and fail back to HTTPS for security.
serverschemelower = str.lower(serverscheme)
if serverschemelower != "http" and serverschemelower != "https":
    print(BColors.WARNING + "No URI scheme found. defaulting to HTTPS.\nWARNING: Requires signed certificate for "
                            "validation, or script breaks on HTTPS." + BColors.ENDC)
    serverschemelower = "https"

# Set root password
print(
    BColors.OKGREEN + "Assuming " + login + " user. If this is not correct please edit 'login' in script header." +
    BColors.ENDC)
password = getpass.getpass("Enter password for " + login + "@" + freenasserver + ": ")

if mode == "create":
    # Prepare dataset IDs for HTTP calls. / needs to be converted to %2F
    parentdatasetid = pool + "%2F" + parentdataset.replace("/", "%2F")
    newdatasetid = parentdatasetid.replace("/", "%2F") + "%2F" + newdataset
    # Prepare NFS mount share path, assuming FreeNAS pool mounts at /mnt.
    newdatasetnfssharepath = "/mnt/" + pool + "/" + parentdataset + "/" + newdataset

    # Convert quota to bytes in 10^2
    quotalower = str.lower(quota)
    # Set to bytes if no other annotation
    quotabytes = quota
    # Convert PiB/PB to bytes
    if quotalower.find("p") != -1:
        quotabytes = int(''.join(filter(str.isdigit, quotalower))) * (1024 ** 5)

    # Convert TiB/TB to bytes
    if quotalower.find("t") != -1:
        quotabytes = int(''.join(filter(str.isdigit, quotalower))) * (1024 ** 4)

    # Convert GiB/GB to bytes
    if quotalower.find("g") != -1:
        quotabytes = int(''.join(filter(str.isdigit, quotalower))) * (1024 ** 3)

    # Convert MiB/MB to bytes
    if quotalower.find("m") != -1:
        quotabytes = int(''.join(filter(str.isdigit, quotalower))) * (1024 ** 2)

    # Convert KiB/KB to bytes
    if quotalower.find("k") != -1:
        quotabytes = int(''.join(filter(str.isdigit, quotalower))) * (1024 ** 1)

    # Validate that parent dataset exists
    parentdatasetexistcall = requests.get(
        serverschemelower + "://" + freenasserver + "/api/v2.0/pool/dataset/id/" + parentdatasetid,
        auth=(login, password)
    )

    if parentdatasetexistcall.status_code != 200:
        print(BColors.FAIL + "ERROR: " + pool + "/" + parentdataset + " DOES NOT EXIST!\n" + BColors.ENDC)
        exit(1)
    else:
        print(BColors.OKGREEN + "VALIDATION: Parent dataset exists, proceeding." + BColors.ENDC)

    # Validate that new dataset does not already exist
    newdatasetexistcall = requests.get(
        serverschemelower + "://" + freenasserver + "/api/v2.0/pool/dataset/id/" + newdatasetid,
        auth=(login, password)
    )
    if newdatasetexistcall.status_code == 200:
        print(BColors.FAIL + "ERROR: " + pool + "/" + parentdataset + "/" + newdataset + " EXISTS!\n" + BColors.ENDC)
        exit(1)
    else:
        print(BColors.OKGREEN + "VALIDATION: New dataset does not yet exist, proceeding." + BColors.ENDC)

    # Validate NFS shares don't exist.
    # Getting list of current NFS shares from server
    currentnfssharesrequest = requests.get(
        serverschemelower + "://" + freenasserver + "/api/v2.0/sharing/nfs",
        auth=(login, password)
    )
    currentnfsshares = json.loads(currentnfssharesrequest.text)

    # Iterate through each share
    for share in currentnfsshares:
        path_list = share["paths"]
        for p in path_list:
            # Filter out shares based on our dataset path, and delete the share IDs for those only.
            if p == newdatasetnfssharepath:
                print(BColors.FAIL + "ERROR: NFS Share " + str(
                    share["networks"]) + " for " + newdatasetnfssharepath + "EXISTS. Aborting." + BColors.ENDC)
                exit(1)
            else:
                if len(nfsnetwork) > 1:
                    print(BColors.OKGREEN + "VALIDATION: All NFS shares for " + newdatasetnfssharepath + "do not "
                                                                                                         "exist yet, "
                                                                                                         "proceeding." +
                          BColors.ENDC)
                else:
                    print(BColors.OKGREEN + "VALIDATION: NFS share for " + newdatasetnfssharepath + "does not exist "
                                                                                                    "yet, "
                                                                                                    "proceeding." +
                          BColors.ENDC)

    print("")

    # Confirm our actions to take
    # Format and print actions, taking into account whether we have a quota and multiple NFS shares
    print(BColors.BOLD + BColors.UNDERLINE + BColors.HEADER + "CONFIRMATION:" + BColors.ENDC)
    if int(''.join(filter(str.isdigit, quota))) != 0:
        print(
            "I will create dataset " + pool + "/" + parentdataset + "/" + newdataset + "with a quota of " + quota + ".")
    else:
        print("I will create dataset " + pool + "/" + parentdataset + "/" + newdataset + "with no quota.")
    # Print NFS share(s) to create.
    # For one share:
    if len(nfsnetwork) == 1:
        print(
            "I will create an NFS share for: " + newdatasetnfssharepath + " for the following host(s):" + nfsnetwork[0])
        if str.lower(nfsmaproot[0]) != "none":
            print("With Maproot User: " + nfsmaproot[0])
        else:
            print("With root_squash enabled (default).")
        print("And comment: " + nfscomment[0])

    # For more than one
    if len(nfsnetwork) > 1:
        print("I will create an NFS share for: " + newdatasetnfssharepath + " for the following hosts:\n")
        i = 0
        while i < len(nfsnetwork):
            print("  NFS Share " + str(i) + ":")
            print("    " + nfsnetwork[i])
            if str.lower(nfsmaproot[i]) != "none":
                print("    With Maproot User: " + nfsmaproot[i])
            else:
                print("    With root_squash enabled (default).")
            print("    And comment: " + nfscomment[i])
            print("")
            i += 1

    confirmed = input(BColors.BOLD + "Proceed? (y/n): " + BColors.ENDC)
    # Check for positive confirmation, and start doing stuff.
    if confirmed.lower() == "y" or confirmed.lower() == "yes":
        # Create the dataset
        createdataset = requests.post(
            serverschemelower + "://" + freenasserver + "/api/v2.0/pool/dataset",
            auth=(login, password),
            data=json.dumps({
                "name": newdatasetid.replace("%2F", "/"),
                "type": "FILESYSTEM",
                "quota": quotabytes
            })
        )
        if createdataset.status_code == 200:
            print(BColors.OKGREEN + "Dataset " + newdatasetid.replace("%2F", "/") + " successfully created." +
                  BColors.ENDC)
        else:
            print(BColors.FAIL + "Dataset creation failure. Exiting." + BColors.ENDC)
            exit(1)
        # TODO: Make a Skel dataset with the default dotfiles.
        # Create NFS shares
        # For one share
        if len(nfsnetwork) == 1:
            nfssharejson = dict(paths=newdatasetnfssharepath.split(), networks=nfsnetwork[0].split(" "))
            if str.lower(nfsmaproot[0]) != "none":
                nfssharejson['maproot_user'] = nfsmaproot[0]

            nfssharejson['comment'] = nfscomment[0]
            createnfsshare = requests.post(
                serverschemelower + "://" + freenasserver + "/api/v2.0/sharing/nfs",
                auth=(login, password),
                data=json.dumps(nfssharejson)
            )
            if createnfsshare.status_code == 200:
                print(BColors.OKGREEN + "NFS share " + nfsnetwork[0] + " successfully created." + BColors.ENDC)
            else:
                print(BColors.FAIL + "ERROR: NFS share " + nfsnetwork[0] + " creation failure. Exiting." + BColors.ENDC)

        # For more than one share
        if len(nfsnetwork) > 1:
            nfssharejson = dict(paths=newdatasetnfssharepath.split(), networks=nfsnetwork[0].split(" "))
            if str.lower(nfsmaproot[0]) != "none":
                nfssharejson['maproot_user'] = nfsmaproot[0]

            nfssharejson['comment'] = nfscomment[0]
            createnfsshare = requests.post(
                serverschemelower + "://" + freenasserver + "/api/v2.0/sharing/nfs",
                auth=(login, password),
                data=json.dumps(nfssharejson)
            )
            if createnfsshare.status_code == 200:
                print(BColors.OKGREEN + "NFS share " + nfsnetwork[0] + " successfully created." + BColors.ENDC)
            else:
                print(BColors.FAIL + "ERROR: NFS share " + nfsnetwork[0] + " creation failure. Exiting." + BColors.ENDC)

            nfssharejson.clear()
            i = 1
            while i < len(nfsnetwork):
                nfssharejson = dict(paths=newdatasetnfssharepath.split(), networks=nfsnetwork[i].split(" "))
                if str.lower(nfsmaproot[i]) != "none":
                    nfssharejson['maproot_user'] = nfsmaproot[i]

                nfssharejson['comment'] = nfscomment[i]
                createnfsshare = requests.post(
                    serverschemelower + "://" + freenasserver + "/api/v2.0/sharing/nfs",
                    auth=(login, password),
                    data=json.dumps(nfssharejson)
                )
                if createnfsshare.status_code == 200:
                    print(BColors.OKGREEN + "NFS share " + nfsnetwork[i] + " successfully created." + BColors.ENDC)
                else:
                    print(BColors.FAIL + "ERROR: NFS share " + nfsnetwork[
                        0] + " creation failure. Exiting." + BColors.ENDC)

                nfssharejson.clear()
                i += 1
    else:
        print(BColors.WARNING + "Action cancelled. Exiting." + BColors.ENDC)
        exit(1)

if mode == "delete":
    # Prepare dataset IDs for HTTP calls. / needs to be converted to %2F
    datasetpath = "/mnt/" + pool + "/" + parentdataset + "/" + newdataset
    datasetid = pool + "%2F" + parentdataset.replace("/", "%2F") + "%2F" + newdataset

    # Validate dataset will be deleted
    datasetexistcall = requests.get(
        serverschemelower + "://" + freenasserver + "/api/v2.0/pool/dataset/id/" + datasetid,
        auth=(login, password)
    )
    if datasetexistcall.status_code != 200:
        print(BColors.FAIL + "ERROR: " + datasetpath + " DOES NOT EXIST!\n" + BColors.ENDC)
        exit(1)
    else:
        print(BColors.OKGREEN + "VALIDATION: " + datasetpath + " exists, proceeding." + BColors.ENDC)

    deleteconfirm = input(
        BColors.WARNING + "Really delete " + datasetpath + "? Confirm by typing \"" + newdataset + "\": " +
        BColors.ENDC)
    if deleteconfirm.lower() == newdataset:
        # Get current NFS shares
        currentnfssharesrequest = requests.get(
            serverschemelower + "://" + freenasserver + "/api/v2.0/sharing/nfs",
            auth=(login, password)
        )
        currentnfsshares = json.loads(currentnfssharesrequest.text)
        # Iterate through each share
        for share in currentnfsshares:
            path_list = share["paths"]
            for p in path_list:
                # Filter out shares based on our dataset path, and delete the share IDs for those only.
                if p == datasetpath:
                    deletenfsshare = requests.delete(
                        serverschemelower + "://" + freenasserver + "/api/v2.0/sharing/nfs/id/" + str(share["id"]),
                        auth=(login, password)
                    )
                    if deletenfsshare.status_code == 200:
                        print(BColors.OKGREEN + "NFS Share " + str(
                            share["networks"]) + " for " + datasetpath + " successfully deleted." + BColors.ENDC)
                    else:
                        print(BColors.FAIL + "ERROR: NFS Share " + str(
                            share["networks"]) + " for " + datasetpath + " FAILED to delete. Aborting." + BColors.ENDC)
                        exit(1)

        # Delete the dataset once all NFS shares are created
        deletedataset = requests.delete(
            serverschemelower + "://" + freenasserver + "/api/v2.0/pool/dataset/id/" + datasetid,
            auth=(login, password)
        )
        if deletedataset.status_code == 200:
            print(BColors.OKGREEN + "Dataset " + datasetpath + " Sucessfully deleted" + BColors.ENDC)
        else:
            print(BColors.FAIL + "ERROR: Dataset " + datasetpath + " FAILED to delete. Aborting" + BColors.ENDC)
            exit(1)

    else:
        print(BColors.FAIL + "ERROR: Confirmation mismatch. Aborting")
        exit(1)