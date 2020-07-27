# FreeNAS / TrueNAS API V2.0 Scripts
Scripts built against FreeNAS and TrueNAS V2.0 of the RESTful API, supporting versions 11.3+.

##Scripts in this repository
- **freenas-nfs-home.py**
    >This script creates and deletes home directories and their associated NFS shares as one command.
    > 
    >Script options include:
    > - adding as many NFS shares as needed with any number of subnets, with optional 'Maproot User'
    > - Setting a quota in any readable format (up to Pebibit integers)
    > - Confirmation review showing the dataset and all NFS shares to be created before execution.
    > - Positive confirmation on deletes, mimicking the FreeNAS UI to prevent accidental dataset removal.