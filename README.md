# MemberGroupControl
Discord.py bot to control and display some groups of server members

---

## DESCRIPTION
This bot allows you to control a large number of people, distributing them into certain groups.
Commands for controlling a bot are limited in use and are determined by the server owner.

## HOW TO
1. To run the application you need to install a bot token.
Open the `env.py` file and paste your token into the token line

```python 
token = "YOUR_TOKEN_HERE"
```

2. Установите все зависимости из файла requirements.txt 

```bash
pip install -r requirements.txt
```
3. Next, you can launch the bot

```bash
sudo docker build  --no-cache -t  bot:version .
```

```bash
sudo docker run --restart=always  -it -d --name "MemberBot" bot:version
```

## COMMAND LIST

### Commands for server owner:

`/set_channel channel_for_list:#list channel_for_logs:#logs` - Set channels for displaying participants and for bot logs
The logs are weak, but at least something


`/allow_access role:@role with bot rights` - Set roles that can control the bot

`/deny_access role:@role with bot rights` - Remove access to the bot from the role

`/allow_list` - Show roles that have access to bot commands


`/download_database` - download the database file

there is also a command for synchronizing commands, but this is more for development
`/synchronization`


### Commands for allowed roles
`/create_group group_name:name priority:0` - create a group. The lower the priority, the higher the group will be.

`/delete_group group:name` - Delete group

`/edit_group group:group new_name:name priority:0` - Change the name and priority of the group

`/list_groups - list of all groups`
  
  
  
`/add_user group:group user:@lamake steam_name:lamake steam_link:https://lamake.ru` - add user

`/remove_user user:@lamake` - remove a user from all groups

`/move_user user:@lamake new_group:group` - move user to another group


`/update_list` - updates the list