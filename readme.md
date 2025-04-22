multi-user text editor


#args to host session: 
 -H [file_path] [username]
#connect to session:
 -C [conn_ip] [username]
#for debug add -D as first arg

#internal message format:

    [sender_username] -E [printed] / user edited

    [sender_username] -M [user_x] [user_y] / user position shifted

    [sender_username] -T [text] / file text

    [sender_username] -U ([username] [user_x] [user_y])*  / users in session

    [sender_username] -C [sender_username] / new user connected to session

    [sender_username] -D / user deleted char

    [sender_username] -NL / user added new line