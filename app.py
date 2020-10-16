import requests
import re
import os
import sys
import shutil
import time
import pyodbc
from os.path import basename
from zipfile import ZipFile
from flask import Flask


app = Flask(__name__)


''' Setup variables '''


''' Set up SQL connection String '''
details = {
        'server' : '192.168.1.xxx',
        'database' : 'TESTDB',
        'username' : 'DBtester',
        'password' : 'Password01'
        }


connect_string = 'DRIVER={{ODBC Driver 13 for SQL Server}};SERVER={server};PORT=1443;DATABASE={database};' \
                 'UID={username};PWD={password}'.format(**details)

''' App variables - to be moved to configuration file '''
parts = []

url = 'http://partbatcher:Password01@192.168.1.XXX:8080/OpenKM/Download?uuid='
idxUrl = 'http://192.168.1.XXX:8080/OpenKM/index?uuid='
dldUrl = 'http://192.168.1.XXX:8080/OpenKM/Download?uuid='

''' Methods/functions '''


''' Adds quotation marks around part number and version for SQL query '''
def addQuotes(rawVariable):
    sqlVariable = "'" + rawVariable + "'"

    return sqlVariable


''' Calls SQL script '''
def getLinks(partNumber, versionNumber):
    links = []
    partNumber = addQuotes(partNumber)
    versionNumber = addQuotes(versionNumber)

    conn = pyodbc.connect(connect_string, autocommit=True)

    cursor = conn.cursor()
    SQL_string = '''SELECT ...<enter your SQL query here and replace this text {} {}>...;'''.format(partNumber, versionNumber)
    print(SQL_string)
    cursor.execute(SQL_string)
    
    for row in cursor:
        #"LINK" or whatever the SQL returned column is that containes link addresses to docs
        row.LINK = row.LINK.replace(dldUrl, url)
        row.LINK = row.LINK.replace(idxUrl, url)
        row.LINK = row.LINK.replace(' ', '')
        row = row.LINK.replace(url, url)
        row = requests.get(row, allow_redirects=True)
        links.append(row)
    cursor.close()
    return links
    
    
'''Gets filenames from OpenKM documents'''
def getFilename_fromCd(cd):
    """ Get filename from content-disposition """
    if not cd:
        return None
    fname = re.findall('filename=(.+)', cd)
    if len(fname) == 0:
        return None
    return fname[0]
    
    
''' Creates a zip folder for temp content '''
def fileZipper(dirName, zfName):
    # create a ZipFile object
    with ZipFile(zfName, 'w') as zipObj:
        try:
            # Iterate over all the files in directory
            for folderName, subfolders, filenames in os.walk(dirName):
                for filename in filenames:
                    # create complete filepath of file in directory
                    filePath = os.path.join(folderName, filename)
                    # Add file to zip
                    zipObj.write(filePath, basename(filePath))
        except:
            print ('Stream interrupted during zip file creation')
        finally:
            zipObj.close()
                

@app.route('/pack/<string:part>&<string:version>&<string:userName>', methods=['POST','GET'] )
def create_pack(part, version, userName):
    version = version.strip()
    #Creates a copy of the version variable to be used in file creation without effecting SQL query
    version_file = version
    if not version_file.isalnum():
        version_file = 'DRAFT'

    packAndGo = part + '_' + version_file + '.zip'
    tempDirRoot = 'temp/'
    copyDir = "/mnt/" + userName + '/pack_go/'
    tempDir = copyDir + 'temp'


    ''' Creates new temp directory if path doesn't exist else increments it '''
    if not os.path.exists(copyDir):
        os.mkdir(copyDir)
        print("Directory " , copyDir ,  " now has the pack")
    else:
        print("If the Directory " , copyDir ,  "was empty it now has the pack, otherwise remove the old pack and try again")
        if not os.path.exists(tempDir):
            os.mkdir(tempDir)
        else:
            print("Directory " , tempDir ,  " already exists")


    ''' Calls getLinks method to populate links from database into parts array '''
    parts = getLinks(part, version)


    ''' For each part document generates a file name and folder name and writes the downloaded files to a temp location '''
    for part in parts:
        print('Correct Links', part)
        filename = getFilename_fromCd(part.headers.get('content-disposition'))
        filename_stripped = filename[1:-1]
        fullPath = os.path.join(tempDir, filename_stripped)
        file = open(fullPath, 'wb')
        file.write(part.content)
        file.close()


    ''' Calls the fileZipper method to create an archive from the contents of the temp folder '''
    fileZipper(tempDir, packAndGo)


    ''' Removes temp folder and contents '''
    shutil.rmtree(tempDir)


    ''' Moves archive from base directory to U: Drive location '''
    migrateArchive = copyDir + packAndGo
    print(migrateArchive)
    if not os.path.exists(migrateArchive):
        shutil.move(packAndGo, copyDir)
        result = "Pack generation successful! Retrieve it from the pack_go directory in your U:Drive"
    else:
        os.remove(migrateArchive)
        shutil.move(packAndGo, copyDir)
        result = "Pack generation succeeded, but an archive with the same name already existed in the " \
                 "pack_go directory in your U: Drive. It has been removed and replaced."
    return result


app.run(host='0.0.0.0', port=8080, debug=False)


