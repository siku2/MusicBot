"""More functionality."""


class GieselaUser:
    """A Giesela user."""

    __slots__ = ["discord_id", "name", "discriminator", "avatar_url", "server", "server_id", "server_name", "member"]

    bot = None
    users = {}

    def __init__(self, discord_id, discriminator, name, avatar_url, server, server_id, server_name, member):
        """Create a new Giesela user."""
        self.discord_id = discord_id
        self.name = name
        self.discriminator = discriminator
        self.avatar_url = avatar_url

        self.server = server
        self.server_id = server_id
        self.server_name = server_name

        self.member = member

    def __str__(self):
        """Return a string version."""
        return "{}@[{}]".format(self.tag, self.server_name)

    @classmethod
    def _cache_user(cls, member):
        cache_key = "{}@{}".format(member.id, member.server.id)

        if cache_key not in cls.users:
            cls.users[cache_key] = cls(member.id, member.discriminator, member.name, member.avatar_url, member.server, member.server.id, member.server.name, member)

        return cls.users[cache_key]

    @classmethod
    def from_member(cls, member):
        """Create a new instance based on its Discord counterpart."""
        return cls._cache_user(member)

    @classmethod
    def from_dict(cls, data):
        """Load instance from a serialised dict."""
        server = cls.bot.get_server(data["server"]["id"])
        member = server.get_member(data["id"])
        return cls.from_member(member)

    @property
    def tag(self):
        """Return the discord tag."""
        return "{}#{}".format(self.name, self.discriminator)

    def to_dict(self):
        """Convert to a serialised dict."""
        return {
            "id": self.discord_id,
            "name": self.name,
            "tag": self.tag,
            "avatar_url": self.avatar_url,
            "server": {
                "id": self.server_id,
                "name": self.server_name,
            }
        }