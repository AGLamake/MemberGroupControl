from __future__ import annotations

import logging
import re
import sqlite3
import traceback
from typing import Union

import discord
from discord import app_commands
from discord.app_commands import commands
from discord.utils import get

import env

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

DATABASE_PATH = 'bot_data.db'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('discord')


# Initialize database
def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            priority INTEGER NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id INTEGER NOT NULL,
            discord_name TEXT NOT NULL,
            steam_name TEXT NOT NULL,
            steam_profile TEXT NOT NULL,
            group_id INTEGER,
            FOREIGN KEY(group_id) REFERENCES groups(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            guild_id INTEGER PRIMARY KEY,
            display_channel_id INTEGER,
            logging_channel_id INTEGER
        )
    ''')
    conn.commit()
    cursor.execute('''CREATE TABLE IF NOT EXISTS permissions (
                      guild_id INTEGER,
                      role_id INTEGER)''')
    conn.commit()
    conn.close()


async def log(msg: str, interaction: discord.Interaction):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(f'SELECT logging_channel_id FROM settings WHERE guild_id = {interaction.guild.id}')

    logger.info(msg)

    logging_chat_id = cursor.fetchone()[0]
    if logging_chat_id is None:
        conn.close()
        return

    conn.close()

    try:
        logging_chat = client.get_channel(logging_chat_id)

        await logging_chat.send(locale_text(locale=interaction.locale, message=msg))
    except Exception as e:
        logger.error(f'Error while sending message to log chat: {e}')


def check_permissions():
    async def predicate(interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            return True
        guild_id = interaction.guild.id
        user_roles = [role.id for role in interaction.user.roles]

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute('SELECT role_id FROM permissions WHERE guild_id = ?', (guild_id,))
        allowed_roles = [row[0] for row in cursor.fetchall()]

        return any(role in allowed_roles for role in user_roles)
    return commands.check(predicate)


async def update_display_channel(interaction: discord.Interaction):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(f'SELECT display_channel_id FROM settings WHERE guild_id = {interaction.guild.id}')
    display_channel_id = cursor.fetchone()[0]
    if display_channel_id is None:
        conn.close()
        return

    channel = client.get_channel(display_channel_id)
    if channel is None:
        conn.close()
        return

    cursor.execute('''
        SELECT g.name, u.discord_id, u.discord_name, u.steam_name, u.steam_profile
        FROM groups g
        LEFT JOIN users u ON g.id = u.group_id
        ORDER BY g.id, u.id
    ''')
    groups = cursor.fetchall()

    current_group = None
    user_count = 1
    msg_number = -1

    def num():
        nonlocal msg_number
        msg_number += 1
        return msg_number

    async def send(msg_num: int, context: str, file=None):
        msgs = [msg async for msg in channel.history(oldest_first=True, limit=500)]
        while True:
            if msg_num <= len(msgs) - 1 and msgs[msg_num].type != discord.MessageType.default:
                msg_num = num()
                continue

            if msg_num > len(msgs) - 1 or len(msgs) == 0:
                await channel.send(content=context, file=file)
                return
            else:
                if msgs[msg_num].author != client.user:
                    msg = msgs[msg_num]
                    await msg.delete()
                    msg_num = num()
                    continue
                else:
                    msg = msgs[msg_num]
                    if file:
                        await msg.edit(content=context, attachments=[file])
                    else:
                        if msg.content != context:
                            await msg.edit(content=context, attachments=[])
                    return

    async def remove_unnecessary(msg_num: int):
        while True:
            msgs = [msg async for msg in channel.history(oldest_first=True, limit=500)]

            if msg_num <= len(msgs) - 1 and msgs[msg_num].type != discord.MessageType.default:
                return await remove_unnecessary(msg_num=num())

            count = len(msgs)
            if msg_num > count - 1:
                return
            else:
                msg = msgs[msg_num]
                await msg.delete()

    try:
        picture = discord.File(fp="logo.png")
        await send(msg_num=num(),
                   context="...........................................................................................................................................",
                   file=picture)
        await send(msg_num=num(),
                   context="...........................................................................................................................................")
    except Exception as e:
        traceback.print_exc()

    await send(msg_num=num(), context="""⫘⫘⫘⫘⫘⫘⫘ **A S T R A   M I L I T A R U M** ⫘⫘⫘⫘⫘⫘⫘

▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
** **""")
    for group in groups:
        group_name, discord_id, discord_name, steam_name, steam_profile = group
        if group_name != current_group:
            if current_group is not None:
                await send(msg_num=num(), context="""** **
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
** **""")
            await send(msg_num=num(), context=f"⫘⫘⫘⫘⫘⫘⫘⫘⫘ `{group_name}` ⫘⫘⫘⫘⫘⫘⫘⫘⫘")
            current_group = group_name

        if discord_id is not None:
            discord_user = await client.fetch_user(discord_id)
            steam = f'<{steam_profile}>' if re.search("(https?://[\w.-]+)", steam_profile) else steam_profile
            content = f"{user_count}. {discord_user.mention} - {steam_name} - {steam}"
            await send(msg_num=num(), context=content)
            user_count += 1

    if current_group is not None:
        await send(msg_num=num(), context="""** **
▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒
** **""")
    await remove_unnecessary(num())
    conn.close()


@tree.command(
    name="load_data",
    description="Load data file",
)
@discord.app_commands.checks.has_permissions(administrator=True)
async def load_data(interaction: discord.Interaction):


    try:
        db = discord.File(fp="bot_data.db")
        await interaction.user.send(file=db)
        await interaction.response.send_message(
            locale_text(locale=interaction.locale, message=f"Sent the database file in private messages."),
            ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(
            locale_text(locale=interaction.locale,
                        message="I cannot send messages to you. Please check your privacy settings."),
            ephemeral=True
        )


@tree.command(
    name="set_display_channel",
    description="Set the channel to display the group list",
)
@discord.app_commands.checks.has_permissions(administrator=True)
async def set_display_channel(interaction: discord.Interaction, display_channel: Union[discord.TextChannel, discord.Thread], logging_chat: discord.TextChannel = None):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(f'''
    INSERT INTO settings (display_channel_id, guild_id, logging_channel_id)
    VALUES ({display_channel.id}, {interaction.guild.id}, {logging_chat.id if logging_chat else 'NULL'})
    ON CONFLICT(guild_id) DO UPDATE SET
        display_channel_id = excluded.display_channel_id,
        logging_channel_id = excluded.logging_channel_id
    ''')
    conn.commit()

    msg = f"<@{interaction.user.id}> set display chat to <#{display_channel.id}>."
    if logging_chat:
        msg += f" Logging chat now in <#{logging_chat.id}>"
    await log(msg=msg, interaction=interaction)

    conn.close()

    await interaction.response.send_message(
        locale_text(locale=interaction.locale, message=f"Display channel set to {display_channel.mention}"), ephemeral=True)
    await update_display_channel(interaction=interaction)


@tree.command(
    name="create_group",
    description="Create a new group",
)
@check_permissions()
async def create_group(interaction: discord.Interaction, group_name: str, priority: int):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO groups (name) VALUES (?, ?)', (group_name, priority))
    conn.commit()

    await log(interaction=interaction, msg=f'<@{interaction.user.id}> created a group `{group_name}` with priority `{priority}`')

    conn.close()

    await interaction.response.send_message(
        locale_text(locale=interaction.locale, message=f"Group `{group_name}` created!"), ephemeral=True)
    await update_display_channel(interaction=interaction)


@tree.command(
    name="delete_group",
    description="Delete an existing group"
)
@check_permissions()
async def delete_group(interaction: discord.Interaction, group_id: int):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute(f'SELECT name FROM groups WHERE id = {group_id}')
    group_name = cursor.fetchone()[0]

    cursor.execute(f'DELETE FROM groups WHERE id = {group_id}', )
    cursor.execute(f'DELETE FROM users WHERE group_id = {group_id}')
    conn.commit()
    conn.close()

    await log(interaction=interaction, msg=f'<@{interaction.user.id}> deleted group `{group_name}`')

    await interaction.response.send_message(
        locale_text(locale=interaction.locale, message=f"Group `{group_name}` deleted!"), ephemeral=True)
    await update_display_channel(interaction=interaction)


@tree.command(
    name="rename_group",
    description="Rename an existing group",
)
@app_commands.describe(group_id="Name of the group")
@check_permissions()
async def rename_group(interaction: discord.Interaction, group_id: int, new_name: str, priority: int):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute(f'SELECT name FROM groups WHERE id = {group_id}')
    group_name = cursor.fetchone()[0]

    cursor.execute(f'UPDATE groups SET name = "{new_name}", priority = {priority} WHERE id = {group_id}')
    conn.commit()
    conn.close()

    await log(interaction=interaction, msg=f'<@{interaction.user.id}> renamed group `{group_name}` to `{new_name}` with priority `{priority}`')

    await interaction.response.send_message(
        locale_text(locale=interaction.locale, message=f"Group `{group_name}` renamed to `{new_name}`!"),
        ephemeral=True)
    await update_display_channel(interaction=interaction)


@tree.command(
    name="add_user",
    description="Add a user to a group",
)
@app_commands.describe(group_id="Name of the group")
@check_permissions()
async def add_user(interaction: discord.Interaction, group_id: int, user: discord.User, steam_name: str,
                   steam_profile: str):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute(f'SELECT name FROM groups WHERE id = {group_id}')
    group_name = cursor.fetchone()[0]

    if group_name is None:
        await interaction.response.send_message(
            locale_text(locale=interaction.locale, message=f"Group with id `{group_id}` does not exist!"),
            ephemeral=True)
        conn.close()
        return

    cursor.execute(f'DELETE FROM users WHERE discord_id = {user.id}')
    cursor.execute(f'''
        INSERT INTO users (discord_id, discord_name, steam_name, steam_profile, group_id)
        VALUES ({user.id}, "{str(user)}", "{steam_name}", "{steam_profile}", {group_id})
    ''')
    conn.commit()
    conn.close()

    await log(interaction=interaction,
        msg=f'<@{interaction.user.id}> added user <@{user.id}> to group `{group_name}`')

    await interaction.response.send_message(
        locale_text(locale=interaction.locale, message=f"User `{user}` added to group `{group_name}`!"), ephemeral=True)
    await update_display_channel(interaction=interaction)


@tree.command(
    name="remove_user",
    description="Remove a user from all groups",
)
@check_permissions()
async def remove_user(interaction: discord.Interaction, user: discord.User):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(f'DELETE FROM users WHERE discord_id = {user.id}')
    conn.commit()
    conn.close()

    await log(interaction=interaction,
        msg=f'<@{interaction.user.id}> removed user <@{user.id}> from all groups')

    await interaction.response.send_message(
        locale_text(locale=interaction.locale, message=f"User `{user}` removed from all groups!"), ephemeral=True)
    await update_display_channel(interaction=interaction)


@tree.command(
    name="move_user",
    description="Move a user to a different group",
)
@check_permissions()
async def move_user(interaction: discord.Interaction, user: discord.User, new_group_id: int):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute(f'SELECT name FROM groups WHERE id = {new_group_id}')
    group_name = cursor.fetchone()[0]

    if new_group_id is None:
        await interaction.response.send_message(
            locale_text(locale=interaction.locale, message=f"Group with id `{new_group_id}` does not exist!"),
            ephemeral=True)
        conn.close()
        return

    cursor.execute(f'UPDATE users SET group_id = {new_group_id} WHERE discord_id = {user.id}')
    conn.commit()
    conn.close()

    await log(interaction=interaction,
        msg=f'<@{interaction.user.id}> moved user <@{user.id}> to `{group_name}`')

    await interaction.response.send_message(
        locale_text(locale=interaction.locale, message=f"User `{user}` moved to group `{group_name}`!"), ephemeral=True)
    await update_display_channel(interaction=interaction)


@tree.command(
    name="list_groups",
    description="List all existing groups",
)
@check_permissions()
async def list_groups(interaction: discord.Interaction):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, priority FROM groups')
    groups = cursor.fetchall()
    conn.close()

    if groups:
        group_list = "\n".join(
            [locale_text(locale=interaction.locale, message=f'**{group[0]}.** `{group[1]}` : *priority = `{group[2]}`*')
             for group in groups])
        await interaction.response.send_message(
            locale_text(locale=interaction.locale, message=f"Existing groups:\n{group_list}"), ephemeral=True)
    else:
        await interaction.response.send_message(locale_text(locale=interaction.locale, message="No groups found."),
                                                ephemeral=True)


@tree.command(name='sync', description='Owner only')
async def sync(interaction: discord.Interaction):
    await tree.set_translator(Translator())
    await tree.sync()
    await interaction.response.send_message(locale_text(locale=interaction.locale, message='Commands syncronized'),
                                            ephemeral=True)


@tree.command(name='update_list', description='Update group list in chanel')
@check_permissions()
async def update_list(interaction: discord.Interaction):
    await update_display_channel(interaction=interaction)
    await interaction.response.send_message(locale_text(locale=interaction.locale, message='Group list updated!'),
                                            ephemeral=True)
    await log(interaction=interaction,
              msg=f'<@{interaction.user.id}> updated group list channel')


@tree.command(name='set_permissions', description='Set roles that will have access to bot commands')
@discord.app_commands.checks.has_permissions(administrator=True)
async def set_permissions(interaction: discord.Interaction, role: discord.Role):
    guild_id = interaction.guild.id
    role_id = role.id

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM permissions WHERE guild_id = ? AND role_id = ?', (guild_id, role_id))
    data = cursor.fetchone()

    await log(interaction=interaction,
        msg=f'<@{interaction.user.id}> set access to <@&{role.id}>')

    if data is None:
        cursor.execute('INSERT INTO permissions (guild_id, role_id) VALUES (?, ?)', (guild_id, role_id))
        conn.commit()
        await interaction.response.send_message(
            locale_text(locale=interaction.locale, message=f'`{role.name}` now have access to bot commands'),
            ephemeral=True)
    else:
        interaction.response.send_message(
            locale_text(locale=interaction.locale, message=f'`{role.name}` already had access to commands'),
            ephemeral=True)


@tree.command(name='remove_permissions', description="Remove the role's access to bot commands")
@discord.app_commands.checks.has_permissions(administrator=True)
async def remove_permissions(interaction: discord.Interaction, role: discord.Role):
    guild_id = interaction.guild.id
    role_id = role.id

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute(f'SELECT * FROM permissions WHERE guild_id = {guild_id} AND role_id = {role_id}')
    data = cursor.fetchone()

    await log(interaction=interaction,
        msg=f'<@{interaction.user.id}> removed access from <@&{role.id}>')

    if data is None:

        await interaction.response.send_message(
            locale_text(locale=interaction.locale, message=f'`{role.name}` did not have access to bot commands'),
            ephemeral=True)
    else:
        cursor.execute(f'DELETE FROM permissions WHERE guild_id = {guild_id} and role_id = {role_id})')
        conn.commit()
        await interaction.response.send_message(
            locale_text(locale=interaction.locale,
                        message=f'`{role.name}` rights to use bot commands have been removed'),
            ephemeral=True)


@tree.command(name='list_permissions', description="Get roles list have access to bot commands")
@discord.app_commands.checks.has_permissions(administrator=True)
async def list_permissions(interaction: discord.Interaction):
    guild_id = interaction.guild.id

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute(f'SELECT * FROM permissions WHERE guild_id = {guild_id}')
    roles = cursor.fetchall()

    if len(roles) <= 0:

        await interaction.response.send_message(locale_text(locale=interaction.locale,
                                                            message=f'There is no roles have access to bot commands in this server'),
                                                ephemeral=True)
    else:
        roles_list = "\n".join(
            [locale_text(locale=interaction.locale,
                         message=f'**{get(interaction.guild.roles, id=role[1]).id}** `{get(interaction.guild.roles, id=role[1]).name}`')
             for role in roles])
        await interaction.response.send_message(
            locale_text(locale=interaction.locale, message=f"Roles have access to bot commands:\n{roles_list}"),
            ephemeral=True)


@add_user.autocomplete("group_id")
@rename_group.autocomplete("group_id")
@delete_group.autocomplete("group_id")
@move_user.autocomplete("new_group_id")
async def group_autocomplete(interaction: discord.Interaction, current: str):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(f'SELECT id, name FROM groups WHERE name LIKE ?', ('%' + current + '%',))
    groups = cursor.fetchall()
    conn.close()

    data = []
    for group in groups:
        data.append(app_commands.Choice(name=group[1], value=group[0]))

    return data


@remove_permissions.error
@list_permissions.error
@set_permissions.error
@update_list.error
@sync.error
@list_groups.error
@move_user.error
@remove_user.error
@add_user.error
@rename_group.error
@delete_group.error
@create_group.error
@set_display_channel.error
@load_data.error
async def on_error(interaction: discord.Interaction, error):
    if isinstance(error, discord.app_commands.errors.MissingPermissions) or isinstance(error, commands.CheckFailure):
        await interaction.response.send_message(locale_text(locale=interaction.locale, message="You do not have permission to use this command."), ephemeral=True)
    elif isinstance(error, discord.Forbidden):
        await interaction.response.send_message(
            locale_text(locale=interaction.locale, message="I cannot send messages to you. Please check your privacy settings."),
            ephemeral=True
        )
    else:
        # Логирование ошибки или выполнение других действий по вашему усмотрению
        raise error


def locale_text(locale: discord.Locale, message: str) -> str:
    if locale is discord.Locale.russian:
        if 'Sent the database file in private messages.' in message:
            message = message.replace('Sent the database file in private messages.', 'Отправил файл базы данных в личные сообщения.')
        if 'Commands syncronized' in message:
            message = message.replace('Commands syncronized', 'Команды синхронизированы')
        if 'priority' in message:
            message = message.replace('priority', 'приоритет')
        if 'Existing groups:' in message:
            message = message.replace('Existing groups:', 'Список групп:')
        if 'No groups found.' in message:
            message = message.replace('No groups found.', 'Группы не найдены.')
        if 'Group with id' in message:
            message = message.replace('Group with id', 'Группа с идентификатором')
        if 'does not exist!' in message:
            message = message.replace('does not exist!', 'не существует!')
        if 'Group list updated!' in message:
            message.replace('Group list updated!', 'Список участников обновлён!')
        if 'User' in message:
            message = message.replace('User', 'Пользователь')
        if 'Group' in message:
            message = message.replace('Group', 'Группа')
        if 'moved to group' in message:
            message = message.replace('moved to group', 'перемещён в группу')
        if 'removed from all groups!' in message:
            message = message.replace('removed from all groups!', 'удалён из всех групп!')
        if 'added to group' in message:
            message = message.replace('added to group', 'добавлен в группу')
        if 'renamed to' in message:
            message = message.replace('renamed to', 'переименована в')
        if 'deleted' in message:
            message = message.replace('deleted', 'удалена')
        if 'created' in message:
            message = message.replace('created', 'создана')
        if 'Display channel set to' in message:
            message = message.replace('Display channel set to', 'Канал отображения установлен в')
        if "now have access to bot commands" in message:
            message = message.replace('now have access to bot commands', 'теперь имеет доступ к командам бота')
        if 'You do not have permission to use this command.' in message:
            message = message.replace('You do not have permission to use this command.', 'У вас нет прав на использование данной команды.')
        if 'Roles have access to bot commands:' in message:
            message = message.replace('Roles have access to bot commands:', 'Роли, имеющие доступ к командам бота')
        if 'rights to use bot commands have been removed':
            message = message.replace('rights to use bot commands have been removed', 'права на использование команд бота были отозваны')
        if 'did not have access to bot commands':
            message = message.replace('did not have access to bot commands', 'не имел прав на использование команд бота')
        if 'already had access to commands':
            message = message.replace('already had access to commands', 'уже имеет доступ к командам бота')
        if 'There is no roles have access to bot commands in this server':
            message = message.replace('There is no roles have access to bot commands in this server', 'На этом сервере нет ролей, которым был бы разрешён доступ к командам бота')
        if 'set display chat to' in message:
            message = message.replace('set display chat to', 'установил канал для отображения списка в')
        if 'Logging chat now in' in message:
            message = message.replace('Logging chat now in', 'Канал для логов теперь в')
        if 'created a group' in message:
            message = message.replace('created a group', 'создал группу')
        if 'with priority' in message:
            message = message.replace('with priority', 'с приоритетом')
        if 'deleted group' in message:
            message = message.replace('deleted group', 'удалил группу')
        if 'renamed group' in message:
            message = message.replace('renamed group', 'переименовал группу')
        if 'to group' in message:
            message = message.replace('to group', 'в группу')
        if 'I cannot send messages to you. Please check your privacy settings.' in message:
            message = message.replace('I cannot send messages to you. Please check your privacy settings.', 'Не могу отправить Вам приватное сообщение. Проверьте настройки приватности.')
        if 'to' in message:
            message = message.replace('to', 'в')
        if 'added user' in message:
            message = message.replace('added user', 'добавил пользователя')
        if 'removed user' in message:
            message = message.replace('removed user', 'удалил пользователя')
        if 'from all groups' in message:
            message = message.replace('from all groups', 'из всех групп')
        if 'moved user' in message:
            message = message.replace('moved user', 'переместил пользователя')
        if 'updated group list channel' in message:
            message = message.replace('updated group list channel', 'обновил канал с группами')
        if 'set access to' in message:
            message = message.replace('set access to', 'добавил доступ к боту для')
        if 'removed access from' in message:
            message = message.replace('removed access from', 'удалил доступ к боту у')
    return message


class Translator(app_commands.Translator):
    async def translate(
            self,
            string: app_commands.locale_str,
            locale: discord.Locale,
            context: app_commands.TranslationContext,
    ) -> str | None:
        message = str(string)
        if locale is discord.Locale.russian:
            if message == 'sync':
                return 'синхронизация'
            elif message == 'Owner only':
                return 'Только для владельца сервера'
            elif message == 'list_groups':
                return 'список_групп'
            elif message == "priority":
                return "приоритет"
            elif message == 'move_user':
                return 'переместить_пользователя'
            elif message == 'Move a user to a different group':
                return 'Переместить пользователя в другую группу'
            elif message == 'user':
                return 'пользователь'
            elif message == 'new_group_id':
                return 'новая_группа'
            elif message == 'List all existing groups':
                return 'Список всех существующих групп'
            elif message == 'group_id':
                return "группа"
            elif message == 'steam_name':
                return "имя_в_стиме"
            elif message == 'steam_profile':
                return "ссылка_на_стим"
            elif message == 'group_name':
                return "название_группы"
            elif message == 'display_channel':
                return "канал_для_списка"
            elif message == 'logging_channel':
                return "канал_для_логов"
            elif message == 'role':
                return 'роль'
            elif message == 'new_name':
                return "новое_название"
            elif message == 'remove_user':
                return 'удалить_пользователя'
            elif message == 'Remove a user from all groups':
                return 'Удалить пользователя из всех групп'
            elif message == 'add_user':
                return 'добавить_пользователя'
            elif message == 'Add a user to a group':
                return 'Добавить пользователя в группу'
            elif message == 'rename_group':
                return 'изменить_группу'
            elif message == 'Rename an existing group':
                return 'Изменить название и приоритет существующей группы'
            elif message == 'delete_group':
                return 'удалить_группу'
            elif message == 'Delete an existing group':
                return 'Удалить существующую группу'
            elif message == 'create_group':
                return 'создать_группу'
            elif message == 'Create a new group':
                return 'Создать новую группу'
            elif message == 'set_display_channel':
                return 'установить_канал'
            elif message == 'Set the channel to display the group list':
                return 'Установить канал, в котором будет отображаться и обновляться список участников всех групп'
            elif message == 'update_list':
                return 'обновить_список'
            elif message == 'Update group list in chanel':
                return 'Обновить список участников в закреплённом канале'
            elif message == 'list_permissions':
                return 'список_разрешённых'
            elif message == 'Get roles list have access to bot commands':
                return 'Показать список ролей, которым разрешён доступ к командам'
            elif message == 'remove_permissions':
                return 'запретить_доступ'
            elif message == "Remove the role's access to bot commands":
                return 'Запретить доступ к командам бота для роли'
            elif message == 'set_permissions':
                return 'разрешить_доступ'
            elif message == 'Set roles that will have access to bot commands':
                return 'Разрешить доступ к командам бота для роли'
            elif message == 'load_data':
                return 'скачать_базу_данных'
            elif message == 'Load data file':
                return 'Скачать файл базы данных с актуальными данными'
            elif message == 'logging_chat':
                return 'канал_для_логов'

        return None


@client.event
async def on_ready():
    await tree.set_translator(Translator())
    await tree.sync()
    logger.info(f'Logged in as {client.user.name} (ID: {client.user.id})')


init_db()
client.run(env.token)
