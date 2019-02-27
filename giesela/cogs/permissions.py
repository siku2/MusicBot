import asyncio
import contextlib
import itertools
import logging
from typing import Iterable, List, Optional, Union, cast

from discord import Colour, Embed, Forbidden, Guild, Member, Role, User
from discord.ext import commands
from discord.ext.commands import Command, Context

from giesela import Giesela, PermissionDenied
from giesela.permission import PermManager, PermissionType, Role as PermRole, RoleContext, RoleTarget, Target, has_permission, perm_tree
from giesela.ui import PromptYesNo, VerticalTextViewer
from giesela.utils import CommandRef

log = logging.getLogger(__name__)


def get_role_target(target: Union[Role, Member, User, str]) -> RoleTarget:
    """Get `RoleTarget` from provided argument.

    Strings can only be used for special values which must be valid
    raises `CommandError` otherwise.
    """
    role_target = RoleTarget(target)

    if isinstance(target, str):
        if not role_target.is_special:
            raise commands.CommandError(f"\"{target}\" is not a special target!")

        try:
            role_target.check()
        except Exception as e:
            raise commands.CommandError(f"Target invalid: {target}")

    return role_target


def get_role_name_with_flair(role: PermRole) -> str:
    """Decorate the role name with markdown depending on the role context."""
    if role.role_context == RoleContext.SUPERGLOBAL:
        return f"**{role.name}**"
    elif role.role_context == RoleContext.GUILD_DEFAULT:
        return f"{role.name} (default)"
    elif role.role_context == RoleContext.GLOBAL:
        return f"*{role.name}*"

    return role.name


def get_required_perms(cmd: Command, *, global_only: bool = False) -> List[PermissionType]:
    """Get the required permission from the has(_global)_permission decorator."""
    if global_only:
        attr = "_required_global_permissions"
    else:
        attr = "_required_permissions"

    try:
        return list(getattr(cmd, attr))
    except AttributeError:
        return []


class Permissions:
    def __init__(self, bot: Giesela) -> None:
        self.bot = bot
        self.perm_manager = PermManager(bot)

        bot.store_reference("perm_manager", self.perm_manager)
        bot.store_reference("ensure_permission", self.ensure_permission)

    async def ensure_permission(self, ctx: Union[Context, User], *keys: PermissionType, global_only: bool = False) -> bool:
        """Make sure the ctx has the given permissions, raise PermissionDenied otherwise."""
        user = ctx.author if isinstance(ctx, Context) else ctx

        has_perm = await self.perm_manager.has(user, *keys, global_only=global_only)
        if has_perm:
            return True
        else:
            keys_str = ", ".join(f"\"{key}\"" for key in keys)
            if global_only:
                text = f"Global permission {keys_str} required!"
            else:
                text = f"Permission {keys_str} required!"

            raise PermissionDenied(text)

    async def ensure_can_edit_role(self, ctx: Union[Context, User], role: PermRole) -> None:
        """Make sure the given ctx is allowed to edit a role"""
        user = ctx.author if isinstance(ctx, Context) else ctx
        can_edit = await self.perm_manager.can_edit_role(user, role)

        if not can_edit:
            raise PermissionDenied(f"Cannot edit role {role.name}!")

    async def __global_check_once(self, ctx: Context) -> bool:
        return all(await asyncio.gather(
            self.ensure_permission(ctx, *get_required_perms(ctx.command, global_only=False), global_only=False),
            self.ensure_permission(ctx, *get_required_perms(ctx.command, global_only=True), global_only=True)
        ))

    async def get_role(self, query: str, guild_id: Union[Context, Guild, int] = None) -> PermRole:
        """Get a role either by its id or its name.
        Raises:
            `CommandError`: No role was found
        """
        if isinstance(guild_id, Context):
            guild_id = guild_id.guild

        if isinstance(guild_id, Guild):
            guild_id = guild_id.id

        role = await self.perm_manager.get_or_search_role_for_guild(query, guild_id)

        if not role:
            raise commands.CommandError(f"Couldn't find role \"{query}\"")

        return role

    @commands.group("role", invoke_without_command=True, aliases=["roles"])
    async def role_group(self, ctx: Context) -> None:
        """Role commands"""
        raise commands.CommandError("WIP")

    async def _role_list_show(self, ctx: Context, roles: Iterable[PermRole]) -> None:
        role_lines: List[str] = []
        for role in roles:
            role_name = get_role_name_with_flair(role)

            role_line = f"- {role_name}"
            role_lines.append(role_line)

        if not role_lines:
            await ctx.send(embed=Embed(description="There are no roles to show", colour=Colour.blue()))
            return

        viewer = VerticalTextViewer(ctx.channel, bot=self.bot, user=ctx.author, content=role_lines)
        await viewer.display()

        with contextlib.suppress(Forbidden):
            await ctx.message.delete()

    async def _role_targets_show(self, ctx: Context, targets: Iterable[Union[Target, RoleTarget]]) -> None:
        guild_id: Optional[int] = ctx.guild.id if ctx.guild else None

        target_lines: List[str] = []
        for target in targets:
            role_target = target.role_target if isinstance(target, Target) else target
            if guild_id and role_target.has_guild_id:
                # don't show other guild's targets
                if guild_id != role_target.guild_id:
                    continue

            real_target = role_target.resolve(self.bot)
            if real_target:
                target_line = f"- {real_target}"
            else:
                target_line = f"- {role_target}"

            target_lines.append(target_line)

        if not target_lines:
            await ctx.send(embed=Embed(description="No targets to show", colour=Colour.blue()))
            return

        viewer = VerticalTextViewer(ctx.channel, bot=self.bot, user=ctx.author, content=target_lines)
        await viewer.display()

        with contextlib.suppress(Forbidden):
            await ctx.message.delete()

    @role_group.group("list", invoke_without_command=True, aliases=["show"])
    async def role_list_group(self, ctx: Context, target: Union[Role, Member, User, str] = None) -> None:
        """List the roles of a target"""
        if not target:
            await self.role_list_guild_cmd.invoke(ctx)
            return

        guild_id = ctx.guild.id if ctx.guild else None
        roles = await self.perm_manager.get_target_roles_for_guild(target, guild_id)
        await self._role_list_show(ctx, roles)

    @role_list_group.command("me")
    async def role_list_me_cmd(self, ctx: Context) -> None:
        """List your roles"""
        guild_id = ctx.guild.id if ctx.guild else None
        roles = await self.perm_manager.get_target_roles_for_guild(ctx.author, guild_id)
        await self._role_list_show(ctx, roles)

    @role_list_group.command("guild")
    async def role_list_guild_cmd(self, ctx: Context) -> None:
        """List the roles of the guild"""
        guild_id = ctx.guild.id if ctx.guild else None
        roles = await self.perm_manager.get_all_roles_for_guild(guild_id, include_global=False)
        await self._role_list_show(ctx, roles)

    @role_list_group.command("all")
    async def role_list_all_cmd(self, ctx: Context) -> None:
        """List all roles"""
        guild_id = ctx.guild.id if ctx.guild else None
        roles = await self.perm_manager.get_all_roles_for_guild(guild_id, include_global=True)
        await self._role_list_show(ctx, roles)

    @role_group.command("create", aliases=["make", "mk"])
    async def role_create_cmd(self, ctx: Context) -> None:
        """"""
        raise commands.CommandError("WIP")

    @role_group.command("remove", aliases=["rm", "delete", "del"])
    async def role_remove_cmd(self, ctx: Context, role: str) -> None:
        """"""
        role = await self.get_role(role, ctx)
        await self.ensure_can_edit_role(ctx, role)

        prompt = PromptYesNo(ctx.channel, bot=self.bot, user=ctx.author, text=f"Do you really want to delete role **{role.name}**")
        if not await prompt:
            return

        await self.perm_manager.delete_role(role)

        embed = Embed(description=f"Role **{role.name}** deleted!", colour=Colour.green())
        await ctx.send(embed=embed)

    @role_group.command("move", aliases=["mv", "setpriority", "setprio"])
    async def role_move_cmd(self, ctx: Context) -> None:
        """Move a role"""
        raise commands.CommandError("WIP")

    @role_group.command("edit", aliases=["change"])
    async def role_edit_cmd(self, ctx: Context, ) -> None:
        """Edit a role"""
        raise commands.CommandError("WIP")

    @has_permission(perm_tree.permissions.roles.assign)
    @role_group.command("assign", aliases=["addtarget", "target+", "@+"])
    async def role_assign_cmd(self, ctx: Context, target: Union[Role, Member, User, str], role: str) -> None:
        """Add a role to a target"""
        role = await self.get_role(role, ctx)
        await self.ensure_can_edit_role(ctx, role)

        role_target = get_role_target(target)
        if role.is_global and role_target.guild_context:
            raise commands.CommandError(f"Can't assign a global role to a guild target! {role.name}")
        elif role.is_guild and not role_target.guild_context:
            raise commands.CommandError(f"Can't assign a guild specific role to a global target! {role.name}")

        await self.perm_manager.role_add_target(role, role_target)

        embed = Embed(description=f"Added {target} to role **{role.name}**", colour=Colour.green())
        await ctx.send(embed=embed)

    @has_permission(perm_tree.permissions.roles.assign)
    @role_group.command("retract", aliases=["removetarget", "rmtarget", "target-", "@-"])
    async def role_retract_cmd(self, ctx: Context, target: Union[Role, Member, User, str], role: str) -> None:
        """Remove a role from a target"""
        role = await self.get_role(role, ctx)
        await self.ensure_can_edit_role(ctx, role)
        role_target = get_role_target(target)

        await self.perm_manager.role_remove_target(role, role_target)

        embed = Embed(description=f"Removed {target} from role **{role.name}**!", colour=Colour.green())
        await ctx.send(embed=embed)

    @role_group.command("targets")
    async def role_targets_cmd(self, ctx: Context, role: str):
        role = await self.get_role(role, ctx)
        targets = await self.perm_manager.get_targets_with_role(role)
        await self._role_targets_show(ctx, targets)

    @commands.group("permission", invoke_without_command=True, aliases=["permissions", "perm", "perms"])
    async def permission_group(self, ctx: Context) -> None:
        """"""
        raise commands.CommandError("WIP")

    @permission_group.command("can", aliases=["may", "has"])
    async def permission_can_cmd(self, ctx: Context, target: Union[Member, User, Role, str], cmd: CommandRef) -> None:
        """Check whether a target can use a command"""
        cmd = cast(Command, cmd)

        if isinstance(target, str):
            if target.lower() in {"me", "i"}:
                target = ctx.author
            else:
                raise commands.CommandError(f"Unknown target: {target}")

        def _get_flattened_perms(global_only: bool) -> List[str]:
            return list(itertools.chain.from_iterable(map(perm_tree.unfold_perm, get_required_perms(cmd, global_only=global_only))))

        global_perms = _get_flattened_perms(True)
        perms = _get_flattened_perms(False)

        missing_global_perms: List[PermissionType] = []
        for perm in global_perms:
            has_perm = await self.perm_manager.has(target, perm, global_only=True)
            if not has_perm:
                missing_global_perms.append(perm)

        missing_perms: List[PermissionType] = []
        for perm in perms:
            has_perm = await self.perm_manager.has(target, perm)
            if not has_perm:
                missing_perms.append(perm)

        if missing_perms or missing_global_perms:
            embed = Embed(description=f"{target} can't use {cmd.qualified_name}", colour=Colour.red())

            if missing_global_perms:
                missing_global_perms = perm_tree.find_shortest_representation(missing_global_perms)
                value = "\n".join(f"- {perm}" for perm in sorted(missing_global_perms))
                embed.add_field(name="Missing global permissions", value=value)

            if missing_perms:
                missing_perms = perm_tree.find_shortest_representation(missing_perms)
                value = "\n".join(f"- {perm}" for perm in sorted(missing_perms))
                embed.add_field(name="Missing permissions", value=value)

            await ctx.send(embed=embed)
        else:
            await ctx.send(embed=Embed(description=f"{target} can use {cmd.qualified_name}", colour=Colour.green()))

    @permission_group.command("render")
    async def permission_render_cmd(self, ctx: Context) -> None:
        """Render the permission tree"""
        embed = Embed(title="Permissions")
        for name, node in perm_tree.__children__.items():
            rendered = "\n".join(node.render())
            embed.add_field(name=name, value=f"```\n{rendered}```", inline=False)

        await ctx.send(embed=embed)

    @commands.is_owner()
    @commands.command("permreload")
    async def reload_perms_from_file(self, ctx: Context) -> None:
        """Reload permissions from file"""
        try:
            await self.perm_manager.load_from_file()
        except Exception as e:
            raise commands.CommandError(f"Couldn't load permission file: `{e}`")

        await ctx.send(embed=Embed(title="Loaded permission file!", colour=Colour.green()))


def setup(bot: Giesela):
    bot.add_cog(Permissions(bot))
