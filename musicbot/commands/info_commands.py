from random import choice
from textwrap import dedent, indent

from discord import Embed

from ..constants import VERSION as BOTVERSION
from ..tungsten import Tungsten
from ..utils import (Response, block_user, command_info, get_dev_changelog,
                     get_dev_version, hex_to_dec, owner_only)


class InfoCommands:
    @command_info("1.9.5", 1477774380, ***REMOVED***
        "3.4.5": (1497616203, "Improved default help message using embeds"),
        "3.6.0": (1497904733, "Fixed weird indent of some help texts"),
        "3.7.0": (1498233256, "Some better help texts"),
        "3.7.1": (1498237739, "Added interactive help"),
        "3.7.4": (1498318916, "Added \"lyrics\" function help text")
    ***REMOVED***)
    async def cmd_help(self, channel, leftover_args):
        """
        ///|Usage
        `***REMOVED***command_prefix***REMOVED***help [command]`
        ///|Explanation
        Logs a help message.
        ///|Interactive
        `***REMOVED***command_prefix***REMOVED***help <query>`
        """
        command = None

        if len(leftover_args) > 0:
            command = " ".join(leftover_args)

        if command:
            cmd = getattr(self, 'cmd_' + command, None)
            if cmd:
                documentation = cmd.__doc__.format(
                    command_prefix=self.config.command_prefix)
                em = Embed(title="*****REMOVED******REMOVED*****".format(command.upper()))
                fields = documentation.split("///")
                if len(fields) < 2:  # backward compatibility
                    return Response(
                        "```\n***REMOVED******REMOVED***```".format(dedent(cmd.__doc__).format(command_prefix=self.config.command_prefix)))

                for field in fields:
                    if field is None or field is "":
                        continue
                    inline = True
                    if field.startswith("(NL)"):
                        inline = False
                        field = field[4:]
                        # print(field)

                    match = re.match(r"\|(.+)\n((?:.|\n)+)", field)
                    if match is None:
                        continue
                    title, text = match.group(1, 2)

                    em.add_field(
                        name="*****REMOVED******REMOVED*****".format(title), value=dedent(text), inline=inline)
                await self.send_message(channel, embed=em)
                return
            else:
                await self.send_typing(channel)
                params = ***REMOVED***
                    "v": date.today().strftime("%d/%m/%y"),
                    "q": command***REMOVED***
                headers = ***REMOVED***
                    "Authorization": "Bearer CU4UAUCKWN37QLXHMBOYZ425NOGBMIYK"***REMOVED***
                resp = requests.get("https://api.wit.ai/message",
                                    params=params, headers=headers)
                data = resp.json()
                entities = data["entities"]

                return Response(json.dumps(entities, indent=4))

        else:
            em = Embed(
                title="GIESELA HELP",
                url="http://siku2.github.io/Giesela/",
                colour=hex_to_dec("#828c51"),
                description="Here are some of the most useful commands,\nYou can always use `***REMOVED***0***REMOVED***help <cmd>` to get more detailed information on a command".
                format(self.config.command_prefix))

            music_commands = "\n".join([
                "`***REMOVED***0***REMOVED***play` play music",
                "`***REMOVED***0***REMOVED***search` search for music",
                "`***REMOVED***0***REMOVED***stream` enqueue a livestream",
                "`***REMOVED***0***REMOVED***pause` pause playback",
                "`***REMOVED***0***REMOVED***resume` resume playback"
                "`***REMOVED***0***REMOVED***volume` change volume",
                "`***REMOVED***0***REMOVED***seek` seek to a timestamp",
                "`***REMOVED***0***REMOVED***fwd` forward time",
                "`***REMOVED***0***REMOVED***rwd` rewind time"
            ]).format(self.config.command_prefix)
            em.add_field(name="Music", value=music_commands, inline=False)

            queue_commands = "\n".join([
                "`***REMOVED***0***REMOVED***queue` show the queue",
                "`***REMOVED***0***REMOVED***history` show playback history",
                "`***REMOVED***0***REMOVED***np` more information on the current entry",
                "`***REMOVED***0***REMOVED***skip` skip to the next entry in queue",
                "`***REMOVED***0***REMOVED***replay` replay the current entry",
                "`***REMOVED***0***REMOVED***repeat` change repeat mode",
                "`***REMOVED***0***REMOVED***remove` remove entry from queue",
                "`***REMOVED***0***REMOVED***clear` remove all entries from queue",
                "`***REMOVED***0***REMOVED***shuffle` shuffle the queue",
                "`***REMOVED***0***REMOVED***promote` promote entry to front"
            ]).format(self.config.command_prefix)
            em.add_field(name="Queue", value=queue_commands, inline=False)

            playlist_commands = "\n".join([
                "`***REMOVED***0***REMOVED***playlist` create/edit/list playlists",
                "`***REMOVED***0***REMOVED***addtoplaylist` add entry to playlist",
                "`***REMOVED***0***REMOVED***removefromplaylist` remove entry from playlist"
            ]).format(self.config.command_prefix)
            em.add_field(name="Playlist",
                         value=playlist_commands, inline=False)

            misc_commands = "\n".join([
                "`***REMOVED***0***REMOVED***lyrics` retrieve lyrics for the current song",
                "`***REMOVED***0***REMOVED***random` choose between items",
                "`***REMOVED***0***REMOVED***game` play a game",
                "`***REMOVED***0***REMOVED***ask` ask a question",
                "`***REMOVED***0***REMOVED***c` chat with Giesela"
            ]).format(self.config.command_prefix)
            em.add_field(name="Misc", value=misc_commands, inline=False)

            return Response(embed=em)

    @command_info("1.9.5", 1477774380, ***REMOVED***
        "3.6.1": (1497971656, "Fixed broken line wrap")
    ***REMOVED***)
    async def cmd_ask(self, author, channel, message, leftover_args):
        """
        ///|Usage
        `***REMOVED***command_prefix***REMOVED***ask <query>`
        ///|Explanation
        You can ask anything from science, maths, to culture
        """

        await self.send_typing(channel)
        msgContent = " ".join(leftover_args)

        col = choice(
            [9699539, 4915330, 255, 65280, 16776960, 16744192, 16711680])

        client = Tungsten("EH8PUT-67PJ967LG8")
        res = client.query(msgContent)
        if not res.success:
            await self.safe_send_message(
                channel,
                "Nothing found!"
            )

        for pod in res.pods:
            em = Embed(title=pod.title, colour=col)
            em.set_image(url=pod.format["img"][0]["url"])
            em.set_footer(text=pod.format["img"][0]["alt"])
            await self.send_message(channel, embed=em)

    @command_info("3.4.0", 1497533758, ***REMOVED***
        "3.4.8": (1497650090, "When showing changelogs, two logs can't be on the same line anymore")
    ***REMOVED***)
    async def cmd_commandinfo(self, command):
        """
        ///|Usage
        `***REMOVED***command_prefix***REMOVED***commandinfo <command>`
        ///|Explanation
        More information on a command
        """

        c_info = getattr(self, "cmd_" + command, None)
        if not c_info:
            return Response(
                "Couldn't find a command called \"***REMOVED******REMOVED***\"".format(command))

        try:
            em = Embed(title=command.upper(), colour=hex_to_dec("#ffd700"))
            em.add_field(
                name="Version `***REMOVED******REMOVED***`".format(c_info.version),
                value="`***REMOVED******REMOVED***`\nCommand has been added".format(c_info.timestamp),
                inline=False)

            for cl in c_info.changelog:
                v, t, l = cl
                em.add_field(
                    name="Version `***REMOVED******REMOVED***`".format(v),
                    value="`***REMOVED******REMOVED***`\n***REMOVED******REMOVED***".format(t, l),
                    inline=False)

            return Response(embed=em)
        except:
            return Response(
                "Couldn't find any information on the `***REMOVED******REMOVED***` command".format(
                    command))

    @command_info("3.5.6", 1497819288, ***REMOVED***
        "3.6.2": (1497978696, "references are now clickable"),
        "3.7.6": (1498947694, "fixed a bug which would stop Giesela from executing the command because of underscores in the version name")
    ***REMOVED***)
    async def cmd_version(self, channel):
        """
        ///|Usage
        `***REMOVED***command_prefix***REMOVED***version`
        ///|Explanation
        Some more informat about the current version and what's to come.
        """

        await self.send_typing(channel)
        v_code, v_name = BOTVERSION.split("_", 1)
        dev_code, dev_name = get_dev_version()
        changelog = get_dev_changelog()

        desc = "Current Version is `***REMOVED******REMOVED***`\nDevelopment is at `***REMOVED******REMOVED***`\n\n**What's to come:**\n\n".format(
            BOTVERSION, dev_code + "_" + dev_name)
        desc += "\n".join("● " + l for l in changelog)
        em = Embed(title="Version " + v_name, description=desc,
                   url="https://siku2.github.io/Giesela", colour=hex_to_dec("#67BE2E"))

        return Response(embed=em)