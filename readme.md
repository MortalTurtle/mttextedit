multi-user text editor


#args to host session: 
 -H [file_path]
#connect to session:
 -C [conn_ip]

#internal message format:
    [sender_username] -E [printed] / user edited

    [sender_username] -M [newpos] / user position shifted

    [sender_username] -T [text] / file text

    [sender_username] -C [sender_username] / new user connected to session