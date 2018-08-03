import asyncio

from giesela.utils import Response, command_info
from giesela.webiesela import WebieselaServer


class MiscCommands:

    @command_info("3.8.1", 1499116644)
    async def cmd_register(self, server, author, token):
        """
        ///|Usage
        `{command_prefix}register <token>`
        ///|Explanation
        Use this command in order to use the [Giesela-Website]({web_url}).
        """

        if WebieselaServer.register_information(server.id, author.id, token.lower()):
            return Response("You've successfully registered yourself. Go back to your browser and check it out")
        else:
            return Response(
                "Something went wrong while registering. It could be that your code `{}` is wrong. Please make sure that you've entered it correctly.".format(
                    token.upper()))

    async def cmd_getvideolink(self, player, channel, leftover_args):
        """
        Usage:
            {command_prefix}getvideolink ["pause video"]

        Sends the video link that gets you to the current location of the bot. Use "pause video" as argument to help you sync up the video.
        """

        if not player.current_entry:
            await self.safe_send_message(
                channel,
                "Can't give you a link for DUCKING NOTHING")
            return

        if "pause video" in " ".join(leftover_args).lower():
            player.pause()
            minutes, seconds = divmod(player.progress, 60)
            await self.safe_send_message(
                channel, player.current_entry.url + "#t={0}m{1}s".format(
                    minutes, seconds))
            msg = await self.safe_send_message(
                channel, "Resuming video in a few seconds!")
            await asyncio.sleep(1.5)

            for i in range(5, 0, -1):
                new_msg = "** %s **" if i <= 3 else "%s"
                new_msg %= str(i)

                msg = await self.safe_edit_message(
                    msg, new_msg, send_if_fail=True)
                await asyncio.sleep(1)

            await self.safe_edit_message(
                msg, "Let's continue!", send_if_fail=True)
            player.resume()

        else:
            minutes, seconds = divmod(player.progress + 3, 60)
            await self.safe_send_message(
                channel, player.current_entry.url + "#t={0}m{1}s".format(
                    minutes, seconds))

    @command_info("3.7.3", 1498306682, {
        "3.7.4": (1498312423, "Fixed severe bug and added musixmatch as a source"),
        "3.9.2": (1499709472, "Fixed typo"),
        "4.5.6": (1502185982, "In order to properly make lyrics work with Webiesela, the source is seperated from the lyrics"),
        "4.5.7": (1502186654, "Lyrics are now temporarily cached within the entry")
    })
    async def cmd_lyrics(self, player, channel):
        """
        ///|Usage
        `{command_prefix}lyrics`
        ///|Explanation
        Try to find lyrics for the current entry and display 'em
        """

        await self.send_typing(channel)

        if not player.current_entry:
            return Response("There's no way for me to find lyrics for something that doesn't even exist!")

        title = player.current_entry.title
        lyrics = player.current_entry.lyrics

        if not lyrics:
            return Response("Couldn't find any lyrics for **{}**".format(title))
        else:
            return Response("**{title}**\n\n{lyrics}\n**Lyrics from \"{source}\"**".format(**lyrics))
